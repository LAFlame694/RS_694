from finance.models import CreditAllocation, PaymentAllocation
from datetime import timedelta
from django.utils import timezone
from finance.choices import SourceChoices, PaymentStatus

REVERSAL_WINDOW_DAYS = 30


def is_payment_reversible(payment):

    if payment.status == PaymentStatus.REVERSED:
        raise Exception("This payment has already been reversed")

    cutoff_date = (
        timezone.now().date() -
        timedelta(days=REVERSAL_WINDOW_DAYS)
    )

    if payment.payment_date < cutoff_date:
        return False

    deposit_used = CreditAllocation.objects.filter(
        payment=payment,
        source=SourceChoices.DEPOSIT
    ).exists()

    if deposit_used:
        return False

    return True

def validate_credit_lifo(allocation):
    """
    Ensure the allocation being reversed is the latest for that payment.
    """

    latest = CreditAllocation.objects.filter(
        payment=allocation.payment
    ).order_by('-created_at').first()

    if not latest or latest.id != allocation.id:
        raise Exception(
            "LIFO violation: You must reverse the latest credit allocation first."
        )

def validate_payment_lifo(allocation):
    """
    Ensure the allocation being reversed is the latest for that credit.
    """

    latest = PaymentAllocation.objects.filter(
        payment=allocation.payment
    ).order_by('-created_at').first()

    if not latest or latest.id != allocation.id:
        raise Exception(
            "LIFO violation: You must reverse the latest payment allocation first."
        )

def block_payment_if_credit_exists(payment):
    """
    Prevent reversing payment allocation if credit allocations exist.
    """

    if payment.credit_allocations.exists():
        raise Exception(
            "Cannot reverse payment allocation while credit allocations exists. "
            "Please reverse credit allocations first."
        )