from decimal import Decimal
from django.db import transaction
from django.db.models import Sum

from finance.models import DepositAllocation, CreditAllocation, Payment, LedgerEntry
from billing.models import Invoice
from billing.choices import InvoiceStatus
from finance.choices import SourceChoices, LedgerEntryCategory

import logging

logger = logging.getLogger("deposit")

def get_available_deposit(ledger_account):

    payments = Payment.objects.filter(
        ledger_account=ledger_account,
        ledger_entries__category=LedgerEntryCategory.PAYMENT,
        ledger_entries__reversals__isnull=True
    ).distinct()

    total_available = Decimal("0.00")

    for payment in payments:

        # total deposit allocated
        total_deposit = DepositAllocation.objects.filter(
            payment=payment
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        if total_deposit <= 0:
            continue # no deposit in this payment

        # deposit already used
        used_deposit = CreditAllocation.objects.filter(
            payment=payment,
            source=SourceChoices.DEPOSIT
        ).aggregate(
            total=Sum("amount_applied")
        )["total"] or Decimal("0.00")

        # deposit refunded
        refunded_deposit = LedgerEntry.objects.filter(
            payment=payment,
            category=LedgerEntryCategory.REFUND,
            source=SourceChoices.DEPOSIT,
            reversals__isnull=True
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        # remaining deposit
        remaining = total_deposit - used_deposit - refunded_deposit

        # safety guard
        if remaining < 0:
            logger.error(
                f"Deposit inconsistency detected | payment={payment.id}"
            )
            remaining = Decimal("0.00")
        
        total_available += remaining

    return total_available

@transaction.atomic
def apply_deposit_to_invoice(payment_id, invoice_id, amount):
    """
    Manually apply deposit money to an invoice.

    RULES:
    - Only deposit-allocated funds can be used
    - Cannot exceed available deposit
    - Creates CreditAllocation (reuses system)
    - Updates invoice state
    """

    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        logger.error(f"Payment {payment_id} not found")
        raise Exception("Payment not found")
    
    try:
        invoice = Invoice.objects.get(id=invoice_id)
    except Invoice.DoesNotExist:
        logger.error(f"Invoice {invoice_id} not found")
        raise Exception("Invoice not found")
    
    if amount <= 0:
        logger.error(f"Invalid deposit application amount: {amount}")
        raise Exception("Amount must be greater than zero")
    
    # get total deposit from payment
    total_deposit = DepositAllocation.objects.filter(
        payment=payment
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    # get already used deposit for this payment (via CreditAllocation)
    used_deposit = CreditAllocation.objects.filter(
        payment=payment,
        source=SourceChoices.DEPOSIT
    ).aggregate(
        total=Sum("amount_applied")
    )["total"] or Decimal("0.00")

    available_deposit = total_deposit - used_deposit

    # validation
    if available_deposit <= 0:
        logger.error(f"No available deposit | payment {payment_id}")
        raise Exception("No available deposit")
    
    if amount > available_deposit:
        logger.error(
            f"Deposit overuse attempt | payment={payment.id} | "
            f"requested={amount} | available={available_deposit}"
        )
        raise Exception("Amount exceeds available deposit")
    
    # calculate invoice balance
    payment_allocated = invoice.payment_allocations.aggregate(
        total=Sum("amount_applied")
    )["total"] or Decimal("0.00")

    credit_allocated = invoice.credit_allocations.aggregate(
        total=Sum("amount_applied")
    )["total"] or Decimal("0.00")

    total_paid = payment_allocated + credit_allocated
    balance = invoice.total_amount - total_paid

    if balance <= 0:
        logger.error(f"Invoice {invoice_id} already paid in full")
        raise Exception("Invoice already paid in full")
    
    # prevent overpayment
    amount_to_apply = min(amount, balance)

    # create CreditAllocation
    CreditAllocation.objects.create(
        ledger_account=payment.ledger_account,
        payment=payment,
        invoice=invoice,
        source=SourceChoices.DEPOSIT,
        amount_applied=amount_to_apply
    )

    # update invoice
    new_total_paid = total_paid + amount_to_apply
    invoice.amount_paid = new_total_paid

    if new_total_paid == invoice.total_amount:
        invoice.status = InvoiceStatus.PAID
    else:
        invoice.status = InvoiceStatus.PARTIAL
    
    invoice.save(update_fields=["amount_paid", "status"])

    logger.info(
        f"Deposit applied | payment={payment.id} -> invoice={invoice.id} | "
        f"amount={amount_to_apply} | remaining_deposit={available_deposit - amount_to_apply}"
    )