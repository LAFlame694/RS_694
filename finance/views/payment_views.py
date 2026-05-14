from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from django.core.exceptions import ValidationError

from tenants.models import Tenant
from tenants.choices import TenancyStatus
from properties.models import Property
from finance.forms.payment_forms import RecordPaymentForm

from finance.services.payments.query_services import (
    get_tenant_financial_summary,
    get_unpaid_invoices,
)

from finance.services.payments.payment_services import (
    record_payment_service,
)

@login_required
def search_tenant_for_payment_view(request):

    query = request.GET.get("q", "").strip()
    property_id = request.GET.get("property", "").strip()

    tenants = None

    tenant_queryset = Tenant.objects.filter(
        tenancies__status=TenancyStatus.ACTIVE
    ).distinct().prefetch_related(
        "tenancies__unit__property"
    )

    if query:
        tenant_queryset = tenant_queryset.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(phone_number__icontains=query)
        )
    
    if property_id:
        tenant_queryset = tenant_queryset.filter(
            tenancies__unit__property_id=property_id
        )
    
    if query or property_id:
        tenants = tenant_queryset
    
    properties = Property.objects.filter(
        is_active=True
    ).order_by("name")

    context = {
        "query": query,
        "tenants": tenants,
        "properties": properties,
        "selected_property": property_id,
    }

    # HTMX request
    if request.htmx:
        return render(
            request,
            "payments/partials/tenant_search_results.html",
            context
        )
    
    return render(
        request,
        "payments/search_tenant.html",
        context
    )

@login_required
def record_payment_view(request, tenant_id):
    """
    Display tenant financial summary
    and handle payment recording.
    """

    tenant = get_object_or_404(
        Tenant,
        id=tenant_id
    )

    try:
        financial_summary = get_tenant_financial_summary(
            tenant=tenant
        )

        unpaid_invoices = get_unpaid_invoices(
            tenant=tenant
        )

    except ValidationError as e:
        messages.error(request, str(e))
        return redirect(
            "finance:search_tenant_for_payment"
        )
    
    # handle form submission
    if request.method == "POST":
        
        form = RecordPaymentForm(request.POST)

        if form.is_valid():
            try:
                payment = record_payment_service(
                    tenant=tenant,
                    amount=form.cleaned_data["amount"],
                    payment_date=form.cleaned_data["payment_date"],
                    method=form.cleaned_data["method"],
                    created_by=request.user,
                )

                messages.success(
                    request,
                    f"Payment {payment.reference_code} recorded successfully."
                )

                return redirect(
                    "finance:record_payment",
                    tenant_id=tenant.id,
                )
            
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = RecordPaymentForm()
    
    context = {
        "tenant": tenant,
        "financial_summary": financial_summary,
        "unpaid_invoices": unpaid_invoices,
        "form": form,
    }

    return render(
        request,
        "payments/record_payment.html",
        context
    )