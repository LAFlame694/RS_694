import logging 
from decimal import Decimal, InvalidOperation

from django.db.models import F, Q, Count, Sum
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError

from billing.choices import InvoiceCategory, InvoiceStatus, InvoicePaymentStatus
from billing.models import Invoice
from finance.models import LedgerEntry
from finance.choices import LedgerEntryType, LedgerEntryCategory, SourceChoices
from finance.services.credit_service import apply_available_credit_to_invoices
from  finance.services.tenant_access import get_accessible_tenants

logger = logging.getLogger("billing")


def get_invoice_summary_service(*, user):
    """
    Return invoice summary figures for the user's
    entire accessible portfolio.

    These figures are independent of invoice-list filters.
    """

    accessible_tenants = get_accessible_tenants(user=user)

    today = timezone.localdate()

    summary = Invoice.objects.filter(
        tenancy__tenant__in=accessible_tenants
    ).aggregate(
        issued_invoice_count=Count(
            "id",
            filter=Q(status=InvoiceStatus.ISSUED),
        ),

        outstanding_amount=Sum(
            F("total_amount") - F("amount_paid"),
            filter=Q(
                status=InvoiceStatus.ISSUED,
                amount_paid__lt=F("total_amount"),
            ),
        ),

        overdue_invoice_count=Count(
            "id",
            filter=Q(
                status=InvoiceStatus.ISSUED,
                due_date__lt=today,
                amount_paid__lt=F("total_amount"),
            ),
        ),
    )

    # Return zero instead of None when no outstanding invoices exist.
    summary["outstanding_amount"] = (
        summary["outstanding_amount"] or Decimal("0.00")
    )

    return summary


@transaction.atomic
def update_draft_invoice_service(
    *,
    invoice,
    updated_by,
    category,
    amount,
    due_date,
    billing_period_start=None,
    billing_period_end=None,
    notes="",
):
    """
    Update an existing draft invoice.

    Only invoice details can be edited.
    Issued and cancelled invoices cannot be modified.
    """

    # Lock the invoice before making changes.
    try:
        invoice = Invoice.objects.select_for_update().get(
            pk=invoice.pk
        )
    except Invoice.DoesNotExist:
        raise ValidationError("Invoice does not exist.")

    # Only draft invoices can be edited.
    if invoice.status != InvoiceStatus.DRAFT:
        raise ValidationError(
            "Only draft invoices can be edited."
        )

    # Protect against unexpected financial activity.
    if LedgerEntry.objects.filter(invoice=invoice).exists():
        raise ValidationError(
            "This invoice has financial records and cannot be edited."
        )

    # Validate invoice category.
    if category not in InvoiceCategory.values:
        raise ValidationError("Invalid invoice category.")

    # Convert and validate the invoice amount.
    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Enter a valid invoice amount.")

    if not amount.is_finite() or amount <= Decimal("0.00"):
        raise ValidationError(
            "Invoice amount must be greater than zero."
        )

    # Validate the due date.
    if due_date is None:
        raise ValidationError("Invoice due date is required.")

    if due_date < invoice.issue_date:
        raise ValidationError(
            "Due date cannot be earlier than the invoice date."
        )

    # Validate the billing period.
    if (
        billing_period_start
        and billing_period_end
        and billing_period_start > billing_period_end
    ):
        raise ValidationError(
            "Billing period start cannot be after billing period end."
        )

    # Update editable invoice fields.
    invoice.category = category
    invoice.total_amount = amount
    invoice.due_date = due_date
    invoice.billing_period_start = billing_period_start
    invoice.billing_period_end = billing_period_end
    invoice.notes = notes or ""

    # Save the changes.
    try:
        with transaction.atomic():
            invoice.save(
                update_fields=[
                    "category",
                    "total_amount",
                    "due_date",
                    "billing_period_start",
                    "billing_period_end",
                    "notes",
                ]
            )
    except IntegrityError:
        raise ValidationError(
            "An invoice with this category and billing period "
            "already exists for this account."
        )

    # Log the update.
    logger.info(
        "Draft invoice updated successfully. "
        "Invoice ID: %s | Invoice Number: %s | Updated by: %s",
        invoice.pk,
        invoice.invoice_number,
        updated_by,
    )

    return invoice

def get_invoices_service(
        *,
        user,
        property_id=None,
        invoice_status=None,
        payment_status=None,
        billing_period_start=None,
        billing_period_end=None,
        search=None,
        category=None,
        overdue_only=False,
):
    """
    Retrieve invoices accessible to the requesting user,
    with optional filtering and searching.
    """

    accessible_tenants = get_accessible_tenants(user=user)

    invoices = Invoice.objects.filter(
        tenancy__tenant__in=accessible_tenants
    )

    # Optimize related-object retrieval.
    invoices = invoices.select_related(
        "tenancy__tenant",
        "tenancy__unit__property",
        "ledger_account",
        "created_by",
    )

    # Default to issued invoices.
    if invoice_status is None or invoice_status == "":
        invoice_status = InvoiceStatus.ISSUED

    # Allow ALL when the user explicitly requests every invoice status.
    if invoice_status != "ALL":
        if invoice_status not in InvoiceStatus.values:
            raise ValidationError("Invalid invoice status.")

        invoices = invoices.filter(status=invoice_status)

    # Filter by property.
    if property_id:
        invoices = invoices.filter(
            tenancy__unit__property_id=property_id
        )

    # Filter by payment status.
    if payment_status:
        if payment_status not in InvoicePaymentStatus.values:
            raise ValidationError("Invalid payment status.")

        # Payment status only applies to issued invoices.
        invoices = invoices.filter(status=InvoiceStatus.ISSUED)

        if payment_status == InvoicePaymentStatus.UNPAID:
            invoices = invoices.filter(
                amount_paid=0
            )

        elif payment_status == InvoicePaymentStatus.PARTIAL:
            invoices = invoices.filter(
                amount_paid__gt=0,
                amount_paid__lt=F("total_amount"),
            )

        elif payment_status == InvoicePaymentStatus.PAID:
            invoices = invoices.filter(
                amount_paid__gte=F("total_amount")
            )

    # Filter by billing period.
    if (
        billing_period_start
        and billing_period_end
        and billing_period_start > billing_period_end
    ):
        raise ValidationError(
            "Billing period start cannot be after billing period end."
        )

    if billing_period_start:
        invoices = invoices.filter(
            billing_period_end__gte=billing_period_start
        )

    if billing_period_end:
        invoices = invoices.filter(
            billing_period_start__lte=billing_period_end
        )

    # Search invoice number and tenant information.
    if search:
        search = search.strip()

        if search:
            invoices = invoices.filter(
                Q(invoice_number__icontains=search)
                | Q(tenancy__tenant__first_name__icontains=search)
                | Q(tenancy__tenant__last_name__icontains=search)
                | Q(tenancy__tenant__phone_number__icontains=search)
                | Q(tenancy__tenant__id_number__icontains=search)
            )

    # Filter by invoice category.
    if category:
        if category not in InvoiceCategory.values:
            raise ValidationError("Invalid invoice category.")

        invoices = invoices.filter(category=category)

    # Show overdue invoices only.
    if overdue_only:
        invoices = invoices.filter(
            status=InvoiceStatus.ISSUED,
            due_date__lt=timezone.localdate(),
            amount_paid__lt=F("total_amount"),
        )

    # Return the filtered queryset.
    return invoices.order_by("-issue_date", "-created_at")

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
def issue_invoice_service(*, invoice, issued_by, issue_date=None):

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