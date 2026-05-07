import logging
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from finance.models import (
    Payment,
    CreditAllocation,
    DepositAllocation,
    LedgerEntry,
)
from finance.choices import (
    LedgerEntryType, 
    LedgerEntryCategory,
    SourceChoices
)
from finance.services.deposits import get_available_deposit

logger = logging.getLogger("refund")

@transaction.atomic
def process_deposit_refund(ledger_account, amount, system_user):
    
    amount = Decimal(amount)

    if amount <= 0:
        logger.error(
            f"Invalid refund amount | amount={amount}"
        )
        raise Exception(
            "Refund amount must be greater than zero"
        )
    
    # total available deposit
    total_available = get_available_deposit(ledger_account)

    if amount > total_available:
        logger.error(
            f"Refund exceeds available deposit | "
            f"requested={amount} | available={total_available}"
        )
        raise Exception("Insufficient deposit balance")
    
    logger.info(
        f"Starting deposit refund | "
        f"ledger={ledger_account.id} | amount={amount}"
    )

    remaining_refund = amount

    # FIFO payments
    payments = Payment.objects.filter(
        ledger_account=ledger_account
    ).order_by(
        "created_at",
        "id"
    )

    for payment in payments:
        
        if remaining_refund <= 0:
            break

        # total reserved deposit
        total_deposit = DepositAllocation.objects.filter(
            payment=payment
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        if total_deposit <= 0:
            continue

        # deposit used for damages
        used_deposit = CreditAllocation.objects.filter(
            payment=payment,
            source=SourceChoices.DEPOSIT
        ).aggregate(
            total=Sum("amount_applied")
        )["total"] or Decimal("0.00")

        # deposit already refunded
        refunded_deposit = LedgerEntry.objects.filter(
            payment=payment,
            category=LedgerEntryCategory.REFUND,
            source=SourceChoices.DEPOSIT
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        # available deposit
        available_deposit = (
            total_deposit -
            used_deposit -
            refunded_deposit
        )

        # safety guard
        if available_deposit < 0:
            logger.error(
                f"Deposit inconsistency detected | "
                f"payment={payment.id} | "
                f"available={available_deposit}"
            )
            raise Exception(
                f"Deposit inconsistency detected "
                f"for payment {payment.id}"
            )
        
        if available_deposit <= 0:
            continue

        # refund amount
        amount_to_refund = min(
            available_deposit,
            remaining_refund
        )

        # create refund ledger entry
        LedgerEntry.objects.create(
            ledger_account=ledger_account,
            payment=payment,
            entry_type=LedgerEntryType.CHARGE,
            category=LedgerEntryCategory.REFUND,
            amount=amount,
            source=SourceChoices.DEPOSIT,
            entry_date=timezone.now().date(),
            description=(
                f"Deposit refund | "
                f"payment={payment.id}"
            ),
            created_by=system_user
        )

        remaining_refund -= amount_to_refund

        logger.info(
            f"Deposit refunded | "
            f"payment={payment.id} | "
            f"amount={amount_to_refund} | "
            f"remaining={remaining_refund}"
        )

    # final validation
    if remaining_refund > 0:
        logger.error(
            f"Refund incomplete | "
            f"remaining={remaining_refund}"
        )
        raise Exception(
            "Refund could not not be fully processed"
        )
    
    logger.info(
        f"Deposit refund completed successfully | "
        f"ledger={ledger_account.id} | "
        f"total={amount}"
    )