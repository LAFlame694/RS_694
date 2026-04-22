from decimal import Decimal
from django.db.models import Sum
from django.db import transaction

from finance.models import LedgerEntry, CreditAllocation, PaymentAllocation
from finance.choices import LedgerEntryType, LedgerEntryCategory

from billing.models import Invoice
from billing.choices import InvoiceStatus

import logging

logger = logging.getLogger("reverse")

@transaction.atomic
def reverse_payment(payment):
    """
    Reverse a payment safely.
    - Blocks reversal if any credit has already been used

    steps:
    1. validate reversal safety
    2. reverse ledger entry
    3. Undo payment allocations
    4. Recalculate invoices
    """

    logger.info(f"Starting reversal | payment={payment.id}")

    # 1. get ledger entry
    try:
        ledger_entry = payment.ledger_entry
    except LedgerEntry.DoesNotExist:
        raise Exception("No ledger entry found for this payment")
    
    # 2. prevent double reversal
    if ledger_entry.reversals.exists():
        raise Exception("This payment has already been reversed")
    
    # 3. PROTECTION: Block if credit has already been used
    credit_used = CreditAllocation.objects.filter(
        ledger_account=payment.ledger_account
    ).exists()

    if credit_used:
        raise Exception(
            "Cannot reverse payment. Credit has already been applied to invoices."
        )
    
    # 4. create reversal ledger entry
    reversal_entry = LedgerEntry.objects.create(
        ledger_account=ledger_entry.ledger_account,
        category=LedgerEntryCategory.REVERSAL,
        amount=ledger_entry.amount,
        entry_type=LedgerEntryType.CHARGE, # reverse CREDIT
        related_entry=ledger_entry,
        entry_date=ledger_entry.entry_date,
        created_by=ledger_entry.created_by
    )

    logger.info(
        f"Reversal ledger created | original={ledger_entry.id} | reversal={reversal_entry.id}"
    )

    # 5. get all allocations
    allocations = PaymentAllocation.objects.filter(payment=payment)

    affected_invoices = set()

    for allocation in allocations:
        invoice = allocation.invoice
        affected_invoices.add(invoice.id)

        logger.info(
            f"Reversing allocation | payment={payment.id} -> invoice={invoice.id} | amount={allocation.amount_applied}"
        )

        allocation.delete()

    # 6. recalculate affected invoices
    for invoice_id in affected_invoices:
        invoice = Invoice.objects.get(id=invoice_id)

        payment_total = invoice.payment_allocations.aggregate(
            total=Sum("amount_applied")
        )["total"] or Decimal("0.00")

        credit_total = invoice.credit_allocations.aggregate(
            total=Sum("amount_applied")
        )["total"] or Decimal("0.00")

        total_paid = payment_total + credit_total

        invoice.amount_paid = total_paid

        if total_paid == 0:
            invoice.status = InvoiceStatus.ISSUED
        elif total_paid < invoice.total_amount:
            invoice.status = InvoiceStatus.PARTIAL
        else:
            invoice.status = InvoiceStatus.PAID

        invoice.save(update_fields=["amount_paid", "status"])

        logger.info(
            f"Invoice recalculated | invoice={invoice.id} | paid={total_paid} | status={invoice.status}"
        )
    
    logger.info(
        f"Payment reversal complete | payment={payment.id}"
    )