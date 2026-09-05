from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.core.exceptions import PermissionDenied
from django.contrib import messages

from tenants.models import Tenant
from finance.services.deposits import get_deposit_dashboard
from finance.services.tenant_access import get_accessible_tenants

@login_required
def deposit_search_view(request):

    query = request.GET.get("q", "").strip()

    # do not show the tenants before the user starts typing
    tenants = (
        get_accessible_tenants(
            user=request.user,
            query=query
        )
        if query
        else Tenant.objects.none()
    )

    context = {
        "query": query,
        "tenants": tenants,
    }

    # HTMX request
    if request.headers.get("HX-request"):
        return render(
            request,
            "deposits/_deposit_search_results.html",
            context
        )

    # Normal request
    return render(
        request,
        "deposits/deposit_search.html",
        context
    )

@login_required
def tenant_deposit_view(request, tenant_id):
    try:
        data = get_deposit_dashboard(
            user=request.user,
            tenant_id=tenant_id
        )

        context = {
            "tenant": data["tenant"],
            "tenancy": data["tenancy"],
            "ledger_account": data["ledger_account"],
            "summary": data["summary"],
            "deposit_history": data["deposit_history"],
            "eligible_payments": data["eligible_payments"],
        }

        return render(
            request,
            "deposits/tenant_deposit.html",
            context
        )
    except PermissionDenied as e:
        messages.error(
            request,
            str(e)
        )

        return redirect(
            "finance:deposit_search"
        )