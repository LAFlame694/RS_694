from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from django.core.exceptions import ValidationError

from tenants.models import Tenant, Tenancy
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

from finance.services.payments.payment_history_service import (
    get_accessible_tenants,
    get_tenant_payment_history,
    get_payment_detail,
    get_payment_allocations,
)

# ==================== Views for viewing payments history ====================
@login_required
def payment_search_view(request):

    query = request.GET.get("q", "").strip()

    tenants = []
    has_searched = False

    if query:
        has_searched = True
        tenants = get_accessible_tenants(
            user=request.user,
            query=query
        )

    context = {
        "query": query,
        "tenants": tenants,
        "has_searched": has_searched,
    }

    # HTMX request
    if request.htmx:
        return render(
            request,
            "payments/partials/payment_search_results.html",
            context
        )
    
    return render(
        request,
        "payments/payment_search.html",
        context
    )
    
def tenant_payment_history_view(request, tenant_id):

    try:
        data = get_tenant_payment_history(
            user=request.user,
            tenant_id=tenant_id
        )

        context = {
            "tenant": data["tenant"],
            "payments": data["payments"],
            "ledger_account": data["ledger_account"],
        }

        return render(
            request,
            "payments/tenant_payment_history.html",
            context
        )
    
    except PermissionError as e:
        messages.error(request, str(e))
        return redirect("finance:payment_search")
    
    except Exception as e:
        messages.error(request, "An error occurred while fetching payment history.")
        return redirect("finance:payment_search")

def payment_detail_view(request, payment_id):

    try:
        data = get_payment_detail(
            user=request.user,
            payment_id=payment_id
        )

        context = {
            "payment": data["payment"],
            "ledger_entries": data["ledger_entries"],
            "deposit_allocations": data["deposit_allocations"],
        }

        return render(
            request,
            "payments/payment_detail.html",
            context
        )
    
    except PermissionError as e:
        messages.error(request, str(e))
        return redirect("finance:payment_search")
    
    except Exception as e:
        messages.error(request, str(e))
        return redirect("finance:payment_search")

def payment_allocations_view(request, payment_id):

    try:
        data = get_payment_allocations(
            user=request.user,
            payment_id=payment_id
        )

        context = {
            "payment": data["payment"],
            "payment_allocations": data["payment_allocations"],
            "credit_allocations": data["credit_allocations"],
        }

        return render(
            request,
            "payments/payment_allocations.html",
            context
        )
    
    except PermissionError as e:
        messages.error(request, str(e))
        return redirect("finance:payment_search")
    
    except Exception as e:
        messages.error(request, "An error occurred while fetching payment allocations.")
        return redirect("finance:payment_search")

# ==================== Views for recording payments ====================
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