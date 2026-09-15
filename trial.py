def create_deposit_allocation(
        *,
        ledger_account,
        payment,
        amount,
        created_by,
        created_at=None
):
    
    if created_at is None:
        created_at = timezone.now().date()
    
    # validate amount
    try:
        amount = Decimal(amount)
    except (InvalidOperation, TypeError):
        raise ValidationError(
            "Invalid deposit amount."
        )
    
    if amount <= 0:
        raise ValidationError(
            "Deposit amount must be greater than zero."
        )
    
    if payment.ledger_account != ledger_account:
        raise ValidationError(
            "Payment does not belong to the specified ledger account."
        )
    
    # check available credit 
    available_credit = get_available_credit(ledger_account)

    if amount > available_credit:
        raise ValidationError(
            f"Insufficient available credit. "
            f"Available: {available_credit}"
        )
    
    logger.info(
        f"Creating deposit allocation | "
        f"ledger={ledger_account.id} | "
        f"payment={payment.id} | "
        f"amount={amount}"
    )

    # create allocation record
    deposit_allocation = DepositAllocation.objects.create(
        ledger_account=ledger_account,
        payment=payment,
        amount=amount,
        created_at=created_at
    )

    # create ledger entries
    LedgerEntry.objects.create(
        ledger_account=ledger_account,
        payment=payment,
        category=LedgerEntryCategory.DEPOSIT,
        source=SourceChoices.DEPOSIT,
        entry_type=LedgerEntryType.CHARGE,
        amount=amount,
        entry_date=created_at,
        description=f"Deposit allocation for payment {payment}",
        created_by=created_by
    )

    # create deposit liability entry
    LedgerEntry.objects.create(
        ledger_account=ledger_account,
        payment=payment,
        category=LedgerEntryCategory.LIABILITY,
        source=SourceChoices.DEPOSIT,
        entry_type=LedgerEntryType.CREDIT,
        amount=amount,
        entry_date=created_at,
        description=f"Deposit liability for payment {payment}",
        created_by=created_by
    )

    logger.info(
        f"Deposit allocation created successfully | "
        f"allocation={deposit_allocation.id}"
    )

    return deposit_allocation