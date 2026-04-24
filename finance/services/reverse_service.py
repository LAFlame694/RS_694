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
    Fully reverses a payment.

    1. Reverse credit allocations (internal)
    2. Reverse payment allocations (external)
    3. Reverse ledger entries
    4. Recalculate invices
    """

    logger.info(f" Starting FULL reversal | payment ID={payment.id} | amount={payment.amount}")

    # get ledger entry
    try:
        ledger_entry = payment.ledger_entry
    except LedgerEntry.DoesNotExist:
        logger.error(f" No ledger entry found for payment ID={payment.id}")
        raise Exception("No ledger entry found for this payment")
    
    # prevent double reversal
    if ledger_entry.reversals.exists():
        logger.error(f" Payment ID={payment.id} has already been reversed")
        raise Exception("This payment has already been reversed")
    
    affected_invoices = set()

    # 1. Reverse credit allocations (internal)
    credit_allocations = CreditAllocation.objects.filter(payment=payment)

    for allocation in credit_allocations:
        invoice = allocation.invoice
        affected_invoices.add(invoice.id)

        logger.info(
            f" Reversing credit allocation ID={payment.id} -> invoice={invoice.id} | amount={allocation.amount_applied}"
        )

        allocation.delete()
    
    # 2. Reverse payment allocations (external)
    payment_allocations = PaymentAllocation.objects.filter(payment=payment)

    for allocation in payment_allocations:
        invoice = allocation.invoice
        affected_invoices.add(invoice.id)

        logger.info(
            f" Reversing payment allocation ID={payment.id} -> invoice={invoice.id} | amount={allocation.amount_applied}"
        )

        allocation.delete()
    
    # 3. Reverse ledger entry
    reversal_entry = LedgerEntry.objects.create(
        ledger_account=ledger_entry.ledger_account,
        category=LedgerEntryCategory.REVERSAL,
        amount=-ledger_entry.amount,
        entry_type=LedgerEntryType.CHARGE,
        related_entry=ledger_entry,
        entry_date=ledger_entry.entry_date,
        description=f"Reversal of payment ID={payment.id}",
        created_by=ledger_entry.created_by
    )

    logger.info(
        f"Ledger reversed | original={ledger_entry.id} | reversal={reversal_entry.id}"
        )
    
    # 4. Recalculate invoices
    for invoice_id in affected_invoices:
        invoice = Invoice.objects.get(id=invoice_id)

        payment_total = invoice.payment_allocations.aggregate(
            total=Sum('amount_applied')
        )['total'] or Decimal('0.00')

        credit_total = invoice.credit_allocations.aggregate(
            total=Sum('amount_applied')
        )['total'] or Decimal('0.00')

        total_paid = payment_total + credit_total

        invoice.amount_paid = total_paid

        if total_paid == 0:
            invoice.status = InvoiceStatus.ISSUED
        elif total_paid < invoice.total_amount:
            invoice.status = InvoiceStatus.PARTIAL
        else:
            invoice.status = InvoiceStatus.PAID
        
        invoice.save(update_fields=['amount_paid', 'status'])

        logger.info(
            f"Invoice recalculated | invoice={invoice.id} | paid={total_paid}"
        )

    logger.info(f" FULL reversal completed | payment ID={payment.id}")