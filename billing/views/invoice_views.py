from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.utils.dateparse import parse_date
from django.db.models import Q
from django.utils import timezone

from decimal import Decimal, InvalidOperation

from tenants.models import Tenancy

from billing.choices import InvoiceStatus, InvoiceCategory
from billing.services.invoice_services import (
    get_invoices_service,
    get_invoice_summary_service,
    create_invoice_service,
)

from finance.services.tenant_access import get_accessible_tenants

from properties.services.property_access import get_accessible_properties
# Create your views here.

# invoice_list_view()
@login_required
def invoice_list_view(request):
    """
    Display invoices with filtering, pagination
    and portfolio-wide summary figures.
    """

    # Retrieve properties accessible to the current user.
    properties = get_accessible_properties(request.user)

    # Read filter values from the GET request.
    property_id = request.GET.get("property")
    invoice_status = request.GET.get("status") or None
    payment_status = request.GET.get("payment_status") or None
    category = request.GET.get("category") or None
    search = request.GET.get("search", "").strip()

    billing_period_start = request.GET.get("billing_period_start")
    billing_period_end = request.GET.get("billing_period_end")

    overdue_only = request.GET.get("overdue_only") in (
        "1", "true", "on"
    )

    # Validate the selected property.
    if property_id:
        try:
            property_id = int(property_id)
        except (ValueError, TypeError):
            raise Http404("Invalid property.")

        if not properties.filter(pk=property_id).exists():
            raise Http404("Property not found.")

    # Parse billing period dates.
    try:
        if billing_period_start:
            billing_period_start = parse_date(billing_period_start)

            if billing_period_start is None:
                raise ValidationError(
                    "Invalid billing period start date."
                )

        if billing_period_end:
            billing_period_end = parse_date(billing_period_end)

            if billing_period_end is None:
                raise ValidationError(
                    "Invalid billing period end date."
                )
        
        if (
            billing_period_start 
            and billing_period_end 
            and billing_period_start > billing_period_end
        ):
            raise ValidationError(
                "Billing period start date cannot be after end date."
            )

        # Retrieve filtered invoices.
        invoices = get_invoices_service(
            user=request.user,
            property_id=property_id,
            invoice_status=invoice_status,
            payment_status=payment_status,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            search=search,
            category=category,
            overdue_only=overdue_only,
        )

    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))

        # Fall back to the default issued-invoice list.
        invoice_status = None
        payment_status = None
        category = None
        property_id = None
        billing_period_start = None
        billing_period_end = None
        search = ""
        overdue_only = False

        invoices = get_invoices_service(
            user=request.user
        )

    # Retrieve portfolio-wide summary figures.
    summary = get_invoice_summary_service(
        user=request.user
    )

    # Paginate the invoice queryset.
    paginator = Paginator(invoices, 15)

    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Prepare template context.
    context = {
        "invoices": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,

        "summary": summary,
        "properties": properties,

        "selected_property": property_id,
        "selected_status": invoice_status or InvoiceStatus.ISSUED,
        "selected_payment_status": payment_status,
        "selected_category": category,

        # dropdown choices for filters
        "invoice_status_choices": InvoiceStatus.choices,
        "invoice_category_choices": InvoiceCategory.choices,

        "search_query": search,
        "billing_period_start": billing_period_start,
        "billing_period_end": billing_period_end,
        "overdue_only": overdue_only,

    }

    # Return only the invoice table for HTMX requests.
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "billing/invoices/partials/invoice_table.html",
            context,
        )

    return render(
        request,
        "billing/invoices/invoice_list.html",
        context,
    )

# create_invoice_view()
@login_required
def create_invoice_view(request):
    """
    Create an invoice for an accessible active tenancy.
    """

    accessible_tenants = get_accessible_tenants(
        user=request.user
    )

    today = timezone.localdate()

    # Retrieve only currently active and accessible tenancies.
    tenancies = (
        Tenancy.objects
        .filter(
            tenant__in=accessible_tenants,
            status="ACTIVE",
            start_date__lte=today,
        )
        .filter(
            Q(end_date__isnull=True) |
            Q(end_date__gte=today)
        )
        .select_related(
            "tenant",
            "unit",
            "unit__property",
        )
    )

    context = {
        "tenancies": tenancies,
        "invoice_category_choices": InvoiceCategory.choices,
        "invoice_status_choices": [
            (InvoiceStatus.DRAFT, "Save as Draft"),
            (InvoiceStatus.ISSUED, "Issue Immediately"),
        ],
    }

    if request.method == "POST":

        # Retrieve submitted form values.
        tenancy_id = request.POST.get("tenancy")
        category = request.POST.get("category")
        amount = request.POST.get("amount")
        due_date = request.POST.get("due_date")
        billing_period_start = request.POST.get(
            "billing_period_start"
        )
        billing_period_end = request.POST.get(
            "billing_period_end"
        )
        notes = request.POST.get("notes", "").strip()
        status = request.POST.get(
            "status",
            InvoiceStatus.DRAFT
        )

        # Preserve submitted values if validation fails.
        context["form_data"] = request.POST

        try:
            # Retrieve the selected tenancy while enforcing access.
            if not tenancy_id:
                raise ValidationError(
                    "Please select a tenancy."
                )

            try:
                tenancy_id = int(tenancy_id)
            except (ValueError, TypeError):
                raise ValidationError(
                    "Invalid tenancy selected."
                )

            tenancy = get_object_or_404(
                tenancies,
                pk=tenancy_id
            )

            # Validate the amount.
            try:
                amount = Decimal(amount)
            except (InvalidOperation, TypeError, ValueError):
                raise ValidationError(
                    "Please enter a valid invoice amount."
                )

            if not amount.is_finite() or amount <= Decimal("0.00"):
                raise ValidationError(
                    "Invoice amount must be greater than zero."
                )

            # Parse the dates.
            due_date = parse_date(due_date)

            if due_date is None:
                raise ValidationError(
                    "Please provide a valid due date."
                )

            if billing_period_start:
                billing_period_start = parse_date(
                    billing_period_start
                )

                if billing_period_start is None:
                    raise ValidationError(
                        "Invalid billing period start date."
                    )

            if billing_period_end:
                billing_period_end = parse_date(
                    billing_period_end
                )

                if billing_period_end is None:
                    raise ValidationError(
                        "Invalid billing period end date."
                    )

            # Create the invoice through the service layer.
            invoice = create_invoice_service(
                tenancy=tenancy,
                category=category,
                amount=amount,
                due_date=due_date,
                created_by=request.user,
                status=status,
                billing_period_start=billing_period_start,
                billing_period_end=billing_period_end,
                notes=notes,
            )

            if invoice.status == InvoiceStatus.DRAFT:
                messages.success(
                    request,
                    f"Invoice {invoice.invoice_number} "
                    "was saved successfully as a draft."
                )
            else:
                messages.success(
                    request,
                    f"Invoice {invoice.invoice_number} "
                    "was created and issued successfully."
                )

            return redirect("billing:invoice_list")

        except ValidationError as error:
            messages.error(
                request,
                "; ".join(error.messages)
            )

    return render(
        request,
        "billing/invoices/create_invoice.html",
        context,
    )

# invoice_detail_view()
# update_invoice_view()
# issue_invoice_view()
# cancel_invoice_view()
# delete_invoice_view()


# ==========================================
# BILLING PERIOD / MONTHLY BILLING VIEWS
# ==========================================


# ==========================================
# OTHER BILLING VIEWS
# ==========================================