from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.exceptions import PermissionDenied

from finance.services.tenant_access import get_accessible_tenants
from .credit_service import get_available_credit
from tenants.models import Tenancy
from tenants.choices import TenancyStatus
from finance.models import (
    DepositAllocation, 
    CreditAllocation, 
    LedgerEntry,
    Payment,
)
from billing.choices import InvoiceStatus
from finance.choices import (
    LedgerEntryType, 
    SourceChoices, 
    LedgerEntryCategory
)

import logging

logger = logging.getLogger("deposit")

def get_available_deposit(ledger_account):

    # Total deposit liability created
    deposit_liability = LedgerEntry.objects.filter(
        ledger_account=ledger_account,
        source=SourceChoices.DEPOSIT,
        category=LedgerEntryCategory.LIABILITY,
        entry_type=LedgerEntryType.CREDIT
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    # Money already consumed from deposit
    deposit_consumed = LedgerEntry.objects.filter(
        ledger_account=ledger_account,
        source=SourceChoices.DEPOSIT,
        entry_type=LedgerEntryType.CHARGE
    ).exclude(
        category=LedgerEntryCategory.DEPOSIT
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    available_deposit = (deposit_liability - deposit_consumed)

    if available_deposit <= 0:
        return Decimal("0.00")

    return available_deposit

def get_deposit_summary(ledger_account):

    # Total deposit liability ever created
    total_deposit = LedgerEntry.objects.filter(
        ledger_account=ledger_account,
        source=SourceChoices.DEPOSIT,
        category=LedgerEntryCategory.LIABILITY,
        entry_type=LedgerEntryType.CREDIT
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    # Total deposit money consumed
    total_consumed = LedgerEntry.objects.filter(
        ledger_account=ledger_account,
        source=SourceChoices.DEPOSIT,
        entry_type=LedgerEntryType.CHARGE,
    ).exclude(
        category=LedgerEntryCategory.DEPOSIT
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    # current available deposit
    available_deposit = get_available_deposit(ledger_account)

    return {
        "total_deposit": total_deposit,
        "total_consumed": total_consumed,
        "available_deposit": available_deposit
    }

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

@transaction.atomic
def apply_deposit_to_invoice(
    ledger_account,
    invoice,
    amount,
    created_by,
    payment=None,
    application_date=None
):
    
    logger.info(
        "# ===== Starting deposit application ===== #"
    )

    if application_date is None:
        application_date = timezone.now().date()

    # validate amount
    try:
        amount = Decimal(amount)
    except (InvalidOperation, TypeError):
        logger.warning(
            f"Invalid amount for deposit application | "
            f"amount={amount}"
        )
        raise ValidationError(
            "Invalid amount."
        )

    if amount <= 0:
        logger.warning(
            f"Amount must be greater than zero for deposit application | "
            f"amount={amount}"
        )
        raise ValidationError(
            "Amount must be greater than zero."
        )

    # validate ownership
    if invoice.ledger_account != ledger_account:
        logger.warning(
            f"Invoice {invoice.id} does not belong to ledger account {ledger_account.id}"
        )
        raise ValidationError(
            "Invoice does not belong to this ledger account."
        )

    # available deposit
    available_deposit = get_available_deposit(
        ledger_account
    )

    if amount > available_deposit:
        logger.warning(
            f"Insufficient deposit balance. "
            f"Available: {available_deposit}"
        )
        raise ValidationError(
            f"Insufficient deposit balance. "
            f"Available: {available_deposit}"
        )

    # invoice balance
    invoice_balance = (
        invoice.total_amount -
        invoice.amount_paid
    )

    if invoice_balance <= 0:
        logger.warning(
            f"Invoice {invoice.id} is already fully paid."
        )
        raise ValidationError(
            "Invoice already fully paid."
        )

    amount_to_apply = min(
        amount,
        invoice_balance
    )

    logger.info(
        f"Applying deposit to invoice | "
        f"ledger={ledger_account.id} | "
        f"invoice={invoice.id} | "
        f"amount={amount_to_apply}"
    )

    # create allocation record
    CreditAllocation.objects.create(
        ledger_account=ledger_account,
        payment=payment,
        invoice=invoice,
        source=SourceChoices.DEPOSIT,
        amount_applied=amount_to_apply
    )

    # update invoice
    invoice.amount_paid += amount_to_apply

    if invoice.amount_paid >= invoice.total_amount:
        invoice.status = InvoiceStatus.PAID
    else:
        invoice.status = InvoiceStatus.PARTIAL

    invoice.save(
        update_fields=[
            "amount_paid",
            "status"
        ]
    )

    # consume deposit liability
    LedgerEntry.objects.create(
        ledger_account=ledger_account,
        payment=payment,
        entry_type=LedgerEntryType.CHARGE,
        category=invoice.category,
        source=SourceChoices.DEPOSIT,
        amount=amount_to_apply,
        entry_date=application_date,
        description=(
            f"Deposit applied to invoice "
            f"{invoice.id}"
        ),
        created_by=created_by
    )

    logger.info(
        f"Deposit applied successfully | "
        f"invoice={invoice.id} | "
        f"amount={amount_to_apply}"
    )

    return amount_to_apply

def get_deposit_history(ledger_account):

    entries = LedgerEntry.objects.filter(
        ledger_account=ledger_account,
        source=SourceChoices.DEPOSIT,
    ).exclude(
        category=LedgerEntryCategory.LIABILITY,
        entry_type=LedgerEntryType.CREDIT,
    ).select_related(
        "payment", "invoice", "created_by",
    ).order_by(
        "-entry_date", "-created_at"
    )

    return {
        "entries": entries
    }

def get_deposit_eligible_payments(ledger_account):

    payments = Payment.objects.filter(
        ledger_account=ledger_account,
    ).select_related(
        "created_by",
    ).order_by(
        "-payment_date", "-created_at"
    )

    eligible_payments = []

    for payment in payments:

        # money already used to pay invoices
        payment_allocated = (
            CreditAllocation.objects.filter(
                payment=payment
            ).aggregate(
                total=Sum("amount_applied")
            )["total"] or Decimal("0.00")
        )

        # money already reserved as deposit
        deposit_allocated = (
            DepositAllocation.objects.filter(
                payment=payment
            ).aggregate(
                total=Sum("amount")
            )["total"] or Decimal("0.00")
        )

        eligible_amount = (
            payment.amount - payment_allocated - deposit_allocated
        )

        if eligible_amount > Decimal("0.00"):
            eligible_payments.append({
                "payment": payment,
                "eligible_amount": eligible_amount
            })

    return eligible_payments

def get_deposit_dashboard(*, user, tenant_id):
    """
    Return all deposit information required for a tenant's
    deposit dashboard.
    """

    tenant = get_accessible_tenants(
        user=user
    ).filter(
        id=tenant_id
    ).first()

    if not tenant:
        raise PermissionDenied(
            "You do not have permission to view this tenant's deposit information."
        )


    # get active tenancy
    try:
        tenancy = (
            Tenancy.objects
            .select_related("ledger_account")
            .get(
                tenant=tenant,
                status=TenancyStatus.ACTIVE
            )
        )

    except Tenancy.DoesNotExist:
        raise ValidationError(
            "Tenant does not have an active tenancy."
        )

    ledger_account = tenancy.ledger_account

    # get deposit information
    summary = get_deposit_summary(ledger_account)
    history = get_deposit_history(ledger_account)
    eligible_payments = get_deposit_eligible_payments(ledger_account)

    return {
        "tenant": tenant,
        "tenancy": tenancy,
        "ledger_account": ledger_account,
        "summary": summary,
        "deposit_history": history["entries"],
        "eligible_payments": eligible_payments,
    }