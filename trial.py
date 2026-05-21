def get_available_credit(ledger_account):
    payments = Payment.objects.filter(
        ledger_account=ledger_account,
        ledger_entries__category=LedgerEntryCategory.PAYMENT,
        ledger_entries__reversals__isnull=True
    ).distinct()

    total_available = Decimal("0.00")

    for payment in payments:

        # money used via direct payment allocations
        payment_used = PaymentAllocation.objects.filter(
            payment=payment
        ).aggregate(
            total=Sum("amount_applied")
        )["total"] or Decimal("0.00")

        # money used via credit allocations
        credit_used = CreditAllocation.objects.filter(
            payment=payment,
            source=SourceChoices.NORMAL
        ).aggregate(
            total=Sum("amount_applied")
        )["total"] or Decimal("0.00")

        # deposit reserved from this payment (not available for credit)
        deposit_used = DepositAllocation.objects.filter(
            payment=payment
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        remaining = payment.amount - (
            payment_used + 
            credit_used + 
            deposit_used
        )

        if remaining < 0:
            logger.error(
                f"Credit inconsistency detected | payment={payment.id}"
            )
            remaining = Decimal("0.00")
        

        if remaining > 0:
            total_available += remaining
    
    return total_available

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