from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.utils.dateparse import parse_date

from billing.choices import InvoiceStatus, InvoiceCategory
from finance.choices import PaymentStatus
from billing.services.invoice_services import (
    get_invoices_service,
    get_invoice_summary_service,
)
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
        "payment_status_choices": PaymentStatus.choices,
        "invoice_category_choices": InvoiceCategory.choices,

        "search_query": search,
        "billing_period_start": billing_period_start,
        "billing_period_end": billing_period_end,
        "overdue_only": overdue_only,

    }

    return render(
        request,
        "billing/invoices/invoice_list.html",
        context,
    )



# invoice_detail_view()
# create_invoice_view()
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