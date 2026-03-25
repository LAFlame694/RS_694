import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from finance.models import LedgerEntry, Payment, PaymentAllocation
from finance.choices import LedgerEntryType, LedgerEntryCategory
from billing.models import Invoice
from billing.choices import InvoiceStatus

logger = logging.getLogger("billing")

def apply_payment_to_invoices(payment: Payment):
    """
    Automatically allocates a payment to the oldest unpaid invoices.
    Also updates invoice.amount_paid and invoice.status.
    """

    if payment.amount <= 0:
        logger.warning(f"Payment {payment.id} has invalid amount")
        return
    
    try:
        with transaction.atomic():

            # create ledger entry
            LedgerEntry.objects.create(
                ledger_account=payment.ledger_account,
                category=LedgerEntryCategory.PAYMENT,
                amount=payment.amount,
                entry_type=LedgerEntryType.CREDIT,
                entry_date=payment.payment_date,
                created_by=payment.created_by
            )

            # get unpaid invoices
            invoices = Invoice.objects.filter(
                ledger_account=payment.ledger_account,
                status__in=[
                    InvoiceStatus.ISSUED,
                    InvoiceStatus.PARTIAL
                ]
            ).order_by("issue_date", "id")

            remaining_amount = Decimal(payment.amount)

            logger.info(
                f"Starting allocation | payment={payment.id} | amount={payment.amount}"
            )

            # loop through invoices
            for invoice in invoices:
                if remaining_amount <= 0:
                    break

                # calculate current balance safely
                allocated_sum = invoice.payment_allocations.aggregate(
                    total=Sum("amount_applied")
                )["total"] or Decimal("0.00")

                balance = invoice.total_amount - allocated_sum

                if balance <= 0:
                    continue

                # determine how much to apply
                amount_to_apply = min(balance, remaining_amount)

                # create allocation
                PaymentAllocation.objects.create(
                    payment=payment,
                    invoice=invoice,
                    amount_applied=amount_to_apply
                )

                # update invoice.amount_paid
                invoice.amount_paid += amount_to_apply

                # update invoice.status
                if invoice.amount_paid == invoice.total_amount:
                    invoice.status = InvoiceStatus.PAID
                elif invoice.amount_paid > 0:
                    invoice.status = InvoiceStatus.PARTIAL
                else:
                    invoice.status = InvoiceStatus.ISSUED
                
                invoice.save(update_fields=["amount_paid", "status"])

                # reduce remaining amount
                remaining_amount -= amount_to_apply

                logger.info(
                    f"Allocated {amount_to_apply} | payment={payment.id} -> invoice={invoice.id}"
                )

            # handle overpayment
            if remaining_amount > 0:
                logger.info(
                    f"Overpayment detected | payment={payment.id} | remaining={remaining_amount}"
                )
            
            logger.info(
                f"Allocation comlpete | payment={payment.id}"
            )
    
    except Exception as e:
        logger.error(
            f"Payment allocation failed | payment={payment.id} | error={str(e)}",
            exc_info=True
        )
        raise

