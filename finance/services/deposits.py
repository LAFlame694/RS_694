from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.core.exceptions import PermissionDenied

import logging
import uuid

from finance.services.tenant_access import get_accessible_tenants
from .credit_service import get_available_credit
from tenants.choices import TenancyStatus
from tenants.models import Tenancy
from finance.models import (
    DepositAllocation, 
    LedgerEntry,
    LedgerAccount,
)
from billing.choices import InvoiceStatus
from finance.choices import (
    LedgerEntryType, 
    SourceChoices, 
    LedgerEntryCategory
)

logger = logging.getLogger("deposit")

def get_available_deposit(ledger_account):

    # Total deposit funds created
    deposit_liability = LedgerEntry.objects.filter(
        ledger_account=ledger_account,
        source=SourceChoices.DEPOSIT,
        category=LedgerEntryCategory.LIABILITY,
        entry_type=LedgerEntryType.CREDIT
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    # deposit funds consumed
    deposit_consumed = LedgerEntry.objects.filter(
        ledger_account=ledger_account,
        source=SourceChoices.DEPOSIT,
        entry_type=LedgerEntryType.CHARGE,
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    available_deposit = (
        deposit_liability - deposit_consumed
    )

    if available_deposit <= Decimal("0.00"):
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

@transaction.atomic
def create_deposit_allocation(
    *,
    ledger_account,
    amount,
    created_by,
    created_at=None
):

    """
    Transfers available NORMAL credit into the tenant's
    DEPOSIT pool.

    Deposits are account-level and are not tied to any
    individual payment.

    Financial source of truth:

        NORMAL + CHARGE + DEPOSIT_TRANSFER
            ↓
        reduces available NORMAL credit

        DEPOSIT + CREDIT + LIABILITY
            ↓
        increases available DEPOSIT balance
    """

    if created_at is None:
        created_at = timezone.now()

    # validate amount
    try:
        amount = Decimal(amount)
    except (InvalidOperation, TypeError):
        raise ValidationError("Invalid deposit amount.")

    if amount <= Decimal("0.00"):
        raise ValidationError(
            "Deposit amount must be greater than zero."
        )

    # lock ledger account
    ledger_account = (
        LedgerAccount.objects.select_for_update()
        .get(pk=ledger_account.pk)
    )

    # check available normal credit
    available_credit = get_available_credit(ledger_account)

    if amount > available_credit:
        raise ValidationError(
            f"Insufficient available credit. "
            f"Available: {available_credit}"
        )

    # generate deposit reference
    deposit_reference = (
        f"DEP-{uuid.uuid4().hex[:10].upper()}"
    )

    # create audit record
    deposit_allocation = DepositAllocation.objects.create(
        deposit_reference=deposit_reference,
        ledger_account=ledger_account,
        amount=amount,
        created_by=created_by,
    )

    # consume normal credit
    LedgerEntry.objects.create(
        ledger_account=ledger_account,
        category=LedgerEntryCategory.DEPOSIT_TRANSFER,
        source=SourceChoices.NORMAL,
        entry_type=LedgerEntryType.CHARGE,
        amount=amount,
        entry_date=created_at.date(),
        description=(
            f"Transfer of {amount} from normal credit "
            f"to deposit {deposit_reference}"
        ),
        created_by=created_by,
    )

    # create deposit liability
    LedgerEntry.objects.create(
        ledger_account=ledger_account,
        category=LedgerEntryCategory.LIABILITY,
        source=SourceChoices.DEPOSIT,
        entry_type=LedgerEntryType.CREDIT,
        amount=amount,
        entry_date=created_at.date(),
        description=(
            f"Deposit liability created "
            f"{deposit_reference}"
        ),
        created_by=created_by,
    )

    logger.info(
        "Deposit created successfully | "
        "ledger=%s | reference=%s | amount=%s",
        ledger_account.id,
        deposit_reference,
        amount,
    )

    return {
        "deposit_reference": deposit_reference,
        "amount": amount,
        "deposit_allocation": deposit_allocation,
    }

@transaction.atomic
def apply_deposit_to_invoice(
    *,
    ledger_account,
    invoice,
    amount,
    created_by,
    application_date=None
):

    logger.info(
        "===== Starting deposit application ====="
    )

    if application_date is None:
        application_date = timezone.now().date()

    # validate amount
    try:
        amount = Decimal(amount)
    except (InvalidOperation, TypeError):
        logger.warning(
            "Invalid amount for deposit application | "
            "amount=%s",
            amount,
        )
        raise ValidationError("Invalid amount.")

    if amount <= Decimal("0.00"):
        logger.warning(
            "Deposit application amount must be "
            "greater than zero | amount=%s",
            amount,
        )
        raise ValidationError(
            "Amount must be greater than zero."
        )

    # validate invoice ownership
    if invoice.ledger_account_id != ledger_account.id:
        logger.warning(
            "Invoice does not belong to ledger account | "
            "invoice=%s | ledger=%s",
            invoice.id,
            ledger_account.id,
        )
        raise ValidationError(
            "Invoice does not belong to this ledger account."
        )

    # check available deposit
    available_deposit = get_available_deposit(ledger_account)

    if available_deposit <= Decimal("0.00"):
        logger.warning(
            "No available deposit balance | "
            "ledger=%s",
            ledger_account.id,
        )

        raise ValidationError(
            "No available deposit balance."
        )

    if amount > available_deposit:
        logger.warning(
            "Insufficient deposit balance | "
            "ledger=%s | requested=%s | available=%s",
            ledger_account.id,
            amount,
            available_deposit,
        )

        raise ValidationError(
            f"Insufficient deposit balance. "
            f"Available: {available_deposit}"
        )

    invoice_balance = (
        invoice.total_amount - invoice.amount_paid
    )

    if invoice_balance <= Decimal("0.00"):
        logger.warning(
            "Invoice already fully paid | "
            "invoice=%s",
            invoice.id,
        )

        raise ValidationError(
            "Invoice already fully paid."
        )

    # determine actual amount to apply
    amount_to_apply = min(amount, invoice_balance)

    logger.info(
        "Applying deposit to invoice | "
        "ledger=%s | invoice=%s | amount=%s",
        ledger_account.id,
        invoice.id,
        amount_to_apply,
    )

    # create deposit charge ledger entry
    LedgerEntry.objects.create(
        ledger_account=ledger_account,
        invoice=invoice,
        entry_type=LedgerEntryType.CHARGE,
        category=invoice.category,
        source=SourceChoices.DEPOSIT,
        amount=amount_to_apply,
        entry_date=application_date,
        description=(
            f"Deposit applied to invoice "
            f"{invoice.invoice_number}"
        ),
        created_by=created_by,
    )

    # update invoice
    invoice.amount_paid += amount_to_apply

    if invoice.amount_paid >= invoice.total_amount:
        invoice.amount_paid = invoice.total_amount
        invoice.status = InvoiceStatus.PAID
    else:
        invoice.status = InvoiceStatus.PARTIAL

    invoice.save(
        update_fields=[
            "amount_paid",
            "status",
        ]
    )

    logger.info(
        "Deposit applied successfully | "
        "ledger=%s | invoice=%s | amount=%s | "
        "remaining_deposit=%s",
        ledger_account.id,
        invoice.id,
        amount_to_apply,
        available_deposit - amount_to_apply,
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
        "invoice", "created_by",
    ).order_by(
        "-entry_date", "-created_at"
    )

    return {
        "entries": entries
    }

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

    return {
        "tenant": tenant,
        "tenancy": tenancy,
        "ledger_account": ledger_account,
        "summary": summary,
        "deposit_history": history["entries"],
    }