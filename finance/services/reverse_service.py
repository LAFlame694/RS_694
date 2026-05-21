from decimal import Decimal
from django.db.models import Sum
from django.db import transaction
from django.utils import timezone

from finance.models import LedgerEntry, CreditAllocation, PaymentAllocation, DepositAllocation
from finance.choices import LedgerEntryType, LedgerEntryCategory, SourceChoices, PaymentStatus
from finance.services.accounting_service import settle_account
from finance.services.reversal_utils import (
    block_payment_if_credit_exists,
    validate_credit_lifo,
    validate_payment_lifo,
    is_payment_reversible
)

from billing.models import Invoice
from billing.choices import InvoiceStatus

import logging

logger = logging.getLogger("reverse")

@transaction.atomic
def reverse_deposit_refund(refund_entry_id, system_user):

    try:
        refund_entry = LedgerEntry.objects.select_related(
            "ledger_account",
            "payment"
        ).get(
            id=refund_entry_id,
            category=LedgerEntryCategory.REFUND,
            source=SourceChoices.DEPOSIT
        )
    except LedgerEntry.DoesNotExist:
        logger.error(
            f"Deposit refund entry not found | "
            f"entry={refund_entry_id}"
        )
        raise Exception(
            "Deposit refund entry not found"
        )
    
    # already reversed
    already_reversed = LedgerEntry.objects.filter(
        related_entry=refund_entry
    ).exists()

    if already_reversed:
        logger.error(
            f"Deposit refund already reversed | "
            f"entry={refund_entry.id}"
        )
        raise Exception(
            "Deposit refund already reversed"
        )
    
    logger.info(
        f"Reversing deposit refund | "
        f"entry={refund_entry.id} | "
        f"amount={refund_entry.amount}"
    )

    # create reversal entry
    reversal_entry = LedgerEntry.objects.create(
        ledger_account=refund_entry.ledger_account,
        payment=refund_entry.payment,
        entry_type=LedgerEntryType.CHARGE,
        category=LedgerEntryCategory.REVERSAL,
        source=SourceChoices.DEPOSIT,
        amount=refund_entry.amount,
        entry_date=timezone.now().date(),
        description=(
            f"Reversal of deposit refund "
            f"entry {refund_entry.id}"
        ),
        related_entry=refund_entry,
        created_by=system_user
    )

    logger.info(
        f"Deposit refund reversed successfully | "
        f"refund_entry={refund_entry.id} | "
        f"reversal_entry={reversal_entry.id}"
    )

    return reversal_entry

@transaction.atomic
def reverse_payment_allocation(allocation_id):
    try:
        allocation = PaymentAllocation.objects.select_related(
            "invoice", "payment"
        ).get(id=allocation_id)
    except PaymentAllocation.DoesNotExist:
        logger.error(
            f"Payment allocation ID={allocation_id} does not exist"
        )
        raise Exception("Payment allocation not found")
    
    payment = allocation.payment
    invoice = allocation.invoice

    # block if credit allocations exist
    block_payment_if_credit_exists(payment)
    
    # LIFO check
    validate_payment_lifo(allocation)
    
    logger.info(
        f"Reversing payment allocation | allocation={allocation.id} | "
        f"payment={payment.id} | invoice={invoice.id} | amount={allocation.amount_applied}"
    )

    # Delete allocation
    allocation.delete()

    # Recalculate invoice
    payment_total = invoice.payment_allocations.aggregate(
        total=Sum("amount_applied")
    )['total'] or Decimal('0.00')

    credit_total = invoice.credit_allocations.aggregate(
        total=Sum("amount_applied")
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
        f"Payment allocation reversed successfully | invoice={invoice.id} | new paid={total_paid}"
    )

@transaction.atomic
def reverse_credit_allocation(allocation_id):
    try:
        allocation = CreditAllocation.objects.select_related(
            "invoice", "payment"
        ).get(id=allocation_id)
    except CreditAllocation.DoesNotExist:
        logger.error(
            f"Credit allocation ID={allocation_id} does not exist"
        )
        raise Exception("Credit allocation not found")
    
    payment = allocation.payment
    invoice = allocation.invoice

    # LIFO check
    validate_credit_lifo(allocation)

    logger.info(
        f"Reversing credit allocation | allocation={allocation.id} | "
        f"payment={payment.id} | invoice={invoice.id} | amount={allocation.amount_applied}"
    )

    # Delete allocation
    allocation.delete()

    # Recalculate invoice
    payment_total = invoice.payment_allocations.aggregate(
        total=Sum("amount_applied")
    )['total'] or Decimal('0.00')

    credit_total = invoice.credit_allocations.aggregate(
        total=Sum("amount_applied")
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
        f"Credit allocation reversed successfully | invoice={invoice.id} | new paid={total_paid}"
    )

@transaction.atomic
def reverse_payment(payment, reversed_by, reason=None):
    """
    Fully reverses a payment.

    1. Validate reversibility
    2. Reverse/remove allocations
    3. Create reversal ledger entry
    4. Mark payment reversed
    5. Re-settle account to rebuild allocations cleanly
    """

    if not is_payment_reversible(payment):
        logger.error(f"Payment ID={payment.id} is not reversible")
        raise Exception("This payment cannot be reversed")

    logger.info(f" Starting FULL reversal | payment ID={payment.id} | amount={payment.amount}")

    # get ledger entry
    try:
        ledger_entry = LedgerEntry.objects.get(
            payment=payment,
            category=LedgerEntryCategory.PAYMENT
        )
    except LedgerEntry.DoesNotExist:
        logger.error(
            f"No payment ledger entry found for payment ID={payment.id}"
        )
        raise Exception(
            "No payment ledger entry found for this payment"
        )

    # prevent double reversal
    if ledger_entry.reversals.exists():
        logger.error(
            f" Payment ID={payment.id} has already been reversed"
        )
        raise Exception(
            "This payment has already been reversed"
        )

    # check deposit state
    deposit_allocations = DepositAllocation.objects.filter(
        payment=payment
    )

    for deposit in deposit_allocations:

        # deposit used for damages
        deposit_used = CreditAllocation.objects.filter(
            payment=payment,
            source=SourceChoices.DEPOSIT
        ).exists()

        # deposit refunded
        deposit_refunded = LedgerEntry.objects.filter(
            payment=payment,
            category=LedgerEntryCategory.REFUND,
            source=SourceChoices.DEPOSIT,
            reversals__isnull=True
        ).exists()

        if deposit_used or deposit_refunded:
            logger.error(
                f"Cannot reverse payment ID={payment.id} "
                f"because deposit has already been used/refunded"
            )

            raise Exception(
                "Cannot reverse payment because deposit "
                "has already been used or refunded."
            )
        
    deposit_allocations.delete()

    logger.info(
        f"Unused deposit allocations removed | payment={payment.id}"
    )

    # 1. Reverse credit allocations (internal)
    credit_allocations = CreditAllocation.objects.filter(
        payment=payment
    )

    for allocation in credit_allocations:
        logger.info(
            f"Removing credit allocation | "
            f"payment={payment.id} | "
            f"invoice={allocation.invoice.id} | "
            f"amount={allocation.amount_applied}"
        )

        allocation.delete()
    
    # 2. Reverse payment allocations (external)
    payment_allocations = PaymentAllocation.objects.filter(
        payment=payment
    )

    for allocation in payment_allocations:
        logger.info(
            f"Removing payment allocation | "
            f"payment={payment.id} | "
            f"invoice={allocation.invoice.id} | "
            f"amount={allocation.amount_applied}"
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
    
    # Update payment status
    payment.status = PaymentStatus.REVERSED
    payment.reversed_at = timezone.now()
    payment.reversed_by = reversed_by

    if reason:
        existing_notes = payment.notes or ""

        payment.notes = (
            f"{existing_notes}\n\n"
            f"REVERSAL REASON:\n{reason}"
        ).strip()

    payment.save(
        update_fields=[
            "status",
            "reversed_at",
            "reversed_by",
            "notes"
        ]
    )
    logger.info(
        f"Payment marked reversed | "
        f"payment={payment.id}"
    )

    # rebuild account state
    logger.info(
        f"Re-settling ledger account | "
        f"ledger={payment.ledger_account.id}"
    )

    settle_account(payment.ledger_account)

    logger.info(
        f"FULL reversal completed | "
        f"payment ID={payment.id}"
    )

    return reversal_entry