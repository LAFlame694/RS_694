from finance.models import CreditAllocation, PaymentAllocation

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