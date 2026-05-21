from decimal import Decimal
from django.db.models import Sum
from django.db import transaction

from finance.models import (
    DepositAllocation, 
    CreditAllocation, 
    PaymentAllocation, 
    Payment
)
from billing.models import Invoice
from billing.choices import InvoiceStatus
from finance.models import CreditAllocation, LedgerEntry
from finance.choices import SourceChoices, LedgerEntryCategory, PaymentStatus, LedgerEntryType

import logging

logger = logging.getLogger("credit")

def get_available_credit(ledger_account):

    credits = LedgerEntry.objects.filter(
        ledger_account=ledger_account,
        entry_type=LedgerEntryType.CREDIT,
        source=SourceChoices.NORMAL
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    normal_charges = LedgerEntry.objects.filter(
        ledger_account=ledger_account,
        entry_type=LedgerEntryType.CHARGE,
        source=SourceChoices.NORMAL
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    deposit_charges = LedgerEntry.objects.filter(
        ledger_account=ledger_account,
        entry_type=LedgerEntryType.CHARGE,
        source=SourceChoices.DEPOSIT
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    available = credits - normal_charges - deposit_charges

    return max(available, Decimal("0.00"))

@transaction.atomic
def apply_credit_to_invoices(ledger_account):

    invoices = Invoice.objects.filter(
        ledger_account=ledger_account,
        status__in=[InvoiceStatus.ISSUED, InvoiceStatus.PARTIAL]
    ).order_by("issue_date", "id")

    if not invoices.exists():
        logger.info(
            f"No invoices to apply credit for ledger {ledger_account.id}"
        )
        return
    
    # process payments in FIFO order
    payments = Payment.objects.filter(
        ledger_account=ledger_account,
        status=PaymentStatus.COMPLETED,
    ).order_by("created_at", "id")

    for payment in payments:

        # calculate remaining credit for this payment
        payment_used = PaymentAllocation.objects.filter(
            payment=payment
        ).aggregate(
            total=Sum("amount_applied")
        )["total"] or Decimal("0.00")

        credit_used = CreditAllocation.objects.filter(
            payment=payment,
            source=SourceChoices.NORMAL
        ).aggregate(
            total=Sum("amount_applied")
        )["total"] or Decimal("0.00")

        deposit_used = DepositAllocation.objects.filter(
            payment=payment
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        total_used = payment_used + credit_used + deposit_used

        if total_used > payment.amount:
            logger.error(
                f"Over-allocation detected | payment={payment.id} | "
                f"Payment amount={payment.amount} | total used={total_used}"
            )
            raise Exception("Payment over-allocated. Data inconsistency.")

        remaining_credit = payment.amount - total_used

        if remaining_credit <= 0:
            continue

        logger.info(
            f"Processing payment credit | payment={payment.id} | remaining={remaining_credit}"
        )

        # apply to invoices
        for invoice in invoices:
            if remaining_credit <= 0:
                break

            # already paid (payments + credit)
            payment_allocated = invoice.payment_allocations.aggregate(
                total=Sum("amount_applied")
            )["total"] or Decimal("0.00")

            credit_allocated = invoice.credit_allocations.aggregate(
                total=Sum("amount_applied")
            )["total"] or Decimal("0.00")

            total_paid = payment_allocated + credit_allocated

            balance = invoice.total_amount - total_paid

            if balance <= 0:
                continue

            amount_to_apply = min(balance, remaining_credit)

            # link credit to specific payment
            CreditAllocation.objects.create(
                ledger_account=ledger_account,
                payment=payment,
                invoice=invoice,
                source=SourceChoices.NORMAL,
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
                f"Credit applied {amount_to_apply} | payment={payment.id} -> invoice={invoice.id} | remaining_credit={remaining_credit}"
            )
            
    logger.info(
        f"Credit application complete | ledger={ledger_account.id}"
    )