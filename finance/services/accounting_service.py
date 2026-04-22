import logging
from django.db import transaction

from billing.services.payment_service import apply_payment_to_invoices
from finance.services.credit_service import apply_credit_to_invoices

logger = logging.getLogger("accounting")

@transaction.atomic
def settle_account(ledger_account, payment=None):
    """
    Central orchestrator for account settlement.

    Flow:
    1. Apply payment allocations
    2. Apply remaining credits to invoices

    This ensures:
    - No double allocation
    - Proper ordering (payment first, credit second)
    """

    logger.info(f"--- Settling account {ledger_account.id} ---")

    # 1. Apply payment
    if payment:
        logger.info(f"Applying payment {payment.id}")
        apply_payment_to_invoices(payment)
    
    # 2. Apply credits (always)
    logger.info("Applying available credit")
    apply_credit_to_invoices(ledger_account)

    logger.info(f"--- Settlement complete for {ledger_account} ---")