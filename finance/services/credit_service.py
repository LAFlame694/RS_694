from decimal import Decimal
from django.db import transaction, models
from django.db.models import Sum

from finance.models import LedgerEntry
from billing.models import Invoice
from finance.choices import LedgerEntryType
from billing.choices import InvoiceStatus

import logging

logger = logging.getLogger("billing")

def get_available_credit(ledger_account):
    """
    Calculate available credit from ledger:
    credit = total credits - total charges
    """

    totals = LedgerEntry.objects.filter(
        ledger_account=ledger_account
    ).aggregate(
        total_credit=Sum("amount", filter=models.Q(entry_type=LedgerEntryType.CREDIT)),
        total_charge=Sum("amount", filter=models.Q(entry_type=LedgerEntryType.CHARGE))
    )

    total_credit = totals["total_credit"] or Decimal("0.00")
    total_charge = totals["total_charge"] or Decimal("0.00")

    return total_credit -total_charge

@transaction.atomic
def apply_credit_to_invoices(ledger_account):
    """
    Applies existing credit to unpaid invoices.
    Runs after invoices creation.
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

        # calculate already allocated
        allocated_sum = invoice.payment_allocations.aggregate(
            total=Sum("amount_applied")
        )["total"] or Decimal("0.00")

        balance = invoice.total_amount - allocated_sum

        if balance <= 0:
            continue

        amount_to_apply = min(balance, remaining_credit)

        # avoid duplicate allocations
        invoice.amount_paid += amount_to_apply

        if invoice.amount_paid == invoice.total_amount:
            invoice.status = InvoiceStatus.PAID
        elif invoice.amount_paid > 0:
            invoice.status = InvoiceStatus.PARTIAL
        
        invoice.save(update_fields=["amount_paid", "status"])

        remaining_credit -= amount_to_apply

        logger.info(
            f"Credit applied {amount_to_apply} | invoice={invoice.id}"
        )

    logger.info(
        f"Credit application complete | ledger={ledger_account.id}"
    )