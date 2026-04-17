from decimal import Decimal
from django.db.models import Sum
from django.db import models, transaction

from finance.models import LedgerEntry, CreditAllocation, PaymentAllocation
from finance.choices import LedgerEntryType

from billing.models import Invoice
from billing.choices import InvoiceStatus
from finance.models import CreditAllocation

import logging

logger = logging.getLogger("billing")

def get_available_credit(ledger_account):
    """
    Available credit = total credits - total used 
    (payments + allocations)
    """

    total_credit = LedgerEntry.objects.filter(
        ledger_account=ledger_account,
        entry_type=LedgerEntryType.CREDIT
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    # payments already applied via PaymentAllocation
    payment_used = PaymentAllocation.objects.filter(
        payment__ledger_account=ledger_account
    ).aggregate(
        total=Sum("amount_applied")
    )["total"] or Decimal("0.00")

    # money already applied via CreditAllocation
    used_credit = CreditAllocation.objects.filter(
        ledger_account=ledger_account
    ).aggregate(
        total=Sum("amount_applied")
    )["total"] or Decimal("0.00")

    total_used = payment_used + used_credit

    return total_credit - total_used

@transaction.atomic
def apply_credit_to_invoices(ledger_account):
    """
    Applies available credit safely using CreditAllocation.
    Prevents double application.
    """

    available_credit = get_available_credit(ledger_account)

    if available_credit <= 0:
        logger.info(f"No available credit for ledger {ledger_account.id}")
        return
    
    logger.info(
        f"Applying credit | ledger={ledger_account.id} | credit={available_credit}"
    )

    invoices = Invoice.objects.filter(
        ledger_account=ledger_account,
        status__in=[InvoiceStatus.ISSUED, InvoiceStatus.PARTIAL]
    ).order_by("issue_date", "id")

    remaining_credit = available_credit

    for invoice in invoices:
        if remaining_credit <= 0:
            break

        # payments already applied
        payment_allocated = invoice.payment_allocations.aggregate(
            total=Sum("amount_applied")
        )["total"] or Decimal("0.00")

        # credit already applied
        credit_allocated = invoice.credit_allocations.aggregate(
            total=Sum("amount_applied")
        )["total"] or Decimal("0.00")

        total_paid = payment_allocated + credit_allocated

        balance = invoice.total_amount - total_paid

        if balance <= 0:
            continue

        amount_to_apply = min(balance, remaining_credit)

        # credit allocation
        CreditAllocation.objects.create(
            ledger_account=ledger_account,
            invoice=invoice,
            amount_applied=amount_to_apply
        )

        # update invoice
        invoice.amount_paid = total_paid + amount_to_apply

        if invoice.amount_paid == invoice.total_amount:
            invoice.status = InvoiceStatus.PAID
        else:
            invoice.status = InvoiceStatus.PARTIAL
        
        invoice.save(update_fields=["amount_paid", "status"])

        remaining_credit -= amount_to_apply

        logger.info(
            f"Credit applied {amount_to_apply} | invoice={invoice.id}"
        )
    
    logger.info(
        f"Credit application complete | ledger={ledger_account.id}"
    )