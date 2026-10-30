import logging 
from decimal import Decimal

from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError

from billing.choices import InvoiceCategory, InvoiceStatus
from billing.models import Invoice
from finance.models import LedgerEntry
from finance.choices import LedgerEntryType, LedgerEntryCategory, SourceChoices
from finance.services.credit_service import apply_available_credit_to_invoices

logger = logging.getLogger("billing")

@transaction.atomic
def create_invoice_service(
    *,
    tenancy,
    category,
    amount, 
    due_date,
    created_by,
    status=InvoiceStatus.DRAFT,
    billing_period_start=None,
    billing_period_end=None,
    issue_date=None,
    notes="",
):
    """
    Create an invoice.

    DRAFT invoices do not create charge ledger entries.
    ISSUED invoices create a charge ledger entry and then 
    apply available credit.
    """

    if issue_date is None:
        issue_date = timezone.localdate()

    # validate invoice status
    if status not in {
        InvoiceStatus.DRAFT,
        InvoiceStatus.ISSUED,
    }:

        raise ValidationError(
            "An invoice can only be created as a draft or issued."
        )

    # validate invoice amount.
    if amount is None or amount <= Decimal("0.00"):
        raise ValidationError(
            "Invoice amount must be greater than zero."
        )

    # validate invoice category
    if category not in InvoiceCategory.values:
        raise ValidationError(
            f"Invalid invoice category: {category}"
        )

    # validate dates.
    if due_date < issue_date:
        raise ValidationError(
            "The due date cannot be earlier than the issue date."
        )

    if (
        billing_period_start is not None
        and billing_period_end is not None
        and billing_period_start > billing_period_end
    ):
        raise ValidationError(
            "The billing period start date cannot be later than the end date."
        )

    ledger_account = tenancy.ledger_account

    # create the invoice.
    invoice = Invoice.objects.create(
        tenancy=tenancy,
        ledger_account=ledger_account,
        category=category,
        issue_date=issue_date,
        due_date=due_date,
        billing_period_start=billing_period_start,
        billing_period_end=billing_period_end,
        total_amount=amount,
        status=status,
        created_by=created_by,
        notes=notes
    )

    logger.info(
        "Invoice created | invoice=%s | tenancy=%s | status=%s",
        invoice.id,
        tenancy.id,
        invoice.status
    )

    # drafts must not create collectible charges.
    if invoice.status == InvoiceStatus.DRAFT:
        return invoice

    # record the charge for an issued invoice.
    LedgerEntry.objects.create(
        ledger_account=ledger_account,
        invoice=invoice,
        entry_type=LedgerEntryType.CHARGE,
        category=category,
        amount=amount,
        entry_date=issue_date,
        description=(
            f"{category} charge for "
            f"{billing_period_start} - {billing_period_end}"
        ),
        created_by=created_by,
    )

    logger.info(
        "Invoice charge recorded | invoice=%s | amount=%s",
        invoice.id,
        amount,
    )

    # apply available credit to eligible issued invoices.
    apply_available_credit_to_invoices(
        ledger_account=ledger_account,
        created_by=created_by,
        entry_date=None
    )

    logger.info(
        "Invoice creation completed | invoice=%s",
        invoice.id,
    )

    return invoice

@transaction.atomic
def issue_invoice_service(*, invoice, issued_by, issue_date):

    if issue_date is None:
        issue_date = timezone.localdate()

    # lock the invoice row to prevent concurrent issuance
    try:
        invoice = Invoice.objects.select_for_update().get(
            pk=invoice.pk
        )

    except Invoice.DoesNotExist:
        raise ValidationError("Invoice does not exist.")

    # only draft invoices can be issued.
    if invoice.status != InvoiceStatus.DRAFT:
        raise ValidationError(
            "Only draft invoices can be issued."
        )

    # validate the amount
    if invoice.total_amount <= Decimal("0.00"):
        raise ValidationError(
            "Cannot issue an invoice with an amount of zero or less."
        )

    # validate the due date against the actual issue date.
    if invoice.due_date < issue_date:
        raise ValidationError(
            "The due date cannot be earlier than the issue date."
        )

    # a draft should not already have financial ledger entries
    existing_entries = LedgerEntry.objects.filter(
        invoice=invoice
    ).exists()

    if existing_entries:
        raise ValidationError(
            "This draft already has ledger entries. "
            "Review its financial records before issuing it."
        )

    # update the lifecycle status and actual issue date.
    invoice.status = InvoiceStatus.ISSUED
    invoice.issue_date = issue_date
    invoice.save(
        update_fields=["status", "issue_date"]
    )

    # Record the original invoice charge.
    LedgerEntry.objects.create(
        ledger_account=invoice.ledger_account,
        invoice=invoice,
        entry_type=LedgerEntryType.CHARGE,
        category=invoice.category,
        amount=invoice.total_amount,
        entry_date=issue_date,
        description=(
            f"{invoice.category} charge for "
            f"{invoice.billing_period_start} - "
            f"{invoice.billing_period_end}"
        ),
        created_by=issued_by,
    )

    logger.info(
        "Invoice issued | invoice=%s | issued_by=%s",
        invoice.id,
        issued_by.id,
    )

    # apply available credit after the invoice is issued.
    apply_available_credit_to_invoices(
        ledger_account=invoice.ledger_account,
        created_by=issued_by,
        entry_date=issue_date,
    )

    logger.info(
        "Invoice issuance completed | invoice=%s",
        invoice.id,
    )

    return invoice

@transaction.atomic
def cancel_invoice_service(*, invoice, cancelled_by, cancellation_date=None):
    """Cancel an issued and completely unpaid invoice"""

    if cancellation_date is None:
        cancellation_date = timezone.localdate()

    # lock the invoice before validating or changing it.
    try:
        invoice = Invoice.objects.select_for_update().get(
            pk=invoice.pk
        )
    except Invoice.DoesNotExist:
        raise ValidationError("Invoice does not exist.")

    # only issued invoices may be cancelled.
    if invoice.status != InvoiceStatus.ISSUED:
        raise ValidationError(
            "Only issued invoices can be cancelled."
        )

    # the invoice must be completely unpaid.
    if invoice.payment_status != "UNPAID":
        raise ValidationError(
            "Only unpaid invoices can be cancelled. "
            "Partially paid and fully paid invoices cannot be cancelled"
        )

    # A financial-pool entry indicates credit or other
    # financial activity has been applied to this invoice.
    financial_activity = invoice.ledger_entries.filter(
        source__in=[
            SourceChoices.NORMAL,
            SourceChoices.DEPOSIT,
        ]
    ).exists()

    if financial_activity:
        raise ValidationError(
            "This invoice has financial activity and cannot "
            "be cancelled."
        )

    # find the original invoice charge.
    original_charges = LedgerEntry.objects.select_for_update().filter(
        invoice=invoice,
        entry_type=LedgerEntryType.CHARGE,
        source__isnull=True,
    )

    if original_charges.count() != 1:
        raise ValidationError(
            "Expected excatly one original invoice charge. "
            "Review the ledger before cancelling this invoice."
        )

    original_charge = original_charges.get()

    if original_charge.amount != invoice.total_amount:
        raise ValidationError(
            "The original ledger charge does not match the "
            "invoice amount. Review the ledger before cancelling."
        )

    # preserve the original charge and record its reversal
    LedgerEntry.objects.create(
        ledger_account=invoice.ledger_account,
        invoice=invoice,
        source=None,
        entry_type=LedgerEntryType.CREDIT,
        category=LedgerEntryCategory.REVERSAL,
        amount=original_charge.amount,
        entry_date=cancellation_date,
        description=(
            f"Reversal of invoice {invoice.invoice_number} "
            f"following cancellation"
        ),
        created_by=cancelled_by,
    )

    # mark the invoice as cancelled.
    invoice.status = InvoiceStatus.CANCELLED
    invoice.save(update_fields=["status"])

    logger.info(
        "Invoice cancelled | invoice=%s | cancelled_by=%s",
        invoice.id,
        cancelled_by.id,
    )

    return invoice

@transaction.atomic
def delete_draft_invoice_service(*, invoice, deleted_by):
    """
    Delete a draft invoice only if it has no ledger entries.
    Issued and cancelled invoices must remain in the system
    """

    try:
        invoice = Invoice.objects.select_for_update().get(
            pk=invoice.pk
        )
    except Invoice.DoesNotExist:
        raise ValidationError("Invoice does not exist.")

    # Rule 1: Only draft invoices can be deleted.
    if invoice.status != InvoiceStatus.DRAFT:
        raise ValidationError(
            "Only draft invoices can be deleted."
            "Issued and cancelled invoices must be retained."
        )

    # Rule 2: Never delete an invoice that has ledger entries.
    if invoice.ledger_entries.exists():
        raise ValidationError(
            "This draft invoice has ledger entries. "
            "It cannot be deleted."
            "Review its financial records first."
        )

    invoice_id = invoice.id
    invoice_number = invoice.invoice_number

    invoice.delete()

    logger.info(
        "Draft invoice deleted | invoice_id=%s | "
        "invoice_number=%s | deleted_by=%s",
        invoice_id,
        invoice_number,
        deleted_by.id,
    )