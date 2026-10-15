from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib import messages

from tenants.models import Tenant, Tenancy
from tenants.choices import TenancyStatus
from finance.services.deposits import get_deposit_dashboard, create_deposit_allocation
from finance.services.tenant_access import get_accessible_tenants
from finance.services.credit_service import get_available_credit

def get_deposit_context(*, tenant, tenancy, ledger_account, amount=""):
    return {
        "tenant": tenant,
        "tenancy": tenancy,
        "ledger_account": ledger_account,
        "available_credit": get_available_credit(ledger_account),
        "amount": amount,
    }


@login_required
def create_deposit_view(request, tenant_id):
    """
    Create a deposit for a tenant by transferring available
    NORMAL credit into the tenant's DEPOSIT pool.
    """

    accessible_tenants = get_accessible_tenants(
        request.user
    )

    tenant = get_object_or_404(
        accessible_tenants,
        pk=tenant_id,
    )

    tenancy = get_object_or_404(
        Tenancy.objects.select_related(
            "ledger_account"
        ),
        tenant=tenant,
        status=TenancyStatus.ACTIVE,
    )

    ledger_account = tenancy.ledger_account

    if request.method == "POST":
        amount = request.POST.get("amount")

        try:
            result = create_deposit_allocation(
                ledger_account=ledger_account,
                amount=amount,
                created_by=request.user,
            )

        except ValidationError as exc:
            messages.error(
                request,
                exc.message if hasattr(exc, "message") else str(exc)
            )

            return render(
                request,
                "deposits/create_deposit.html",
                get_deposit_context(
                    tenant=tenant,
                    tenancy=tenancy,
                    ledger_account=ledger_account,
                    amount=amount,
                )
            )

        except Exception:

            messages.error(
                request,
                "An unexpected error occurred while creating the deposit."
            )

            return render(
                request,
                "deposits/create_deposit.html",
                get_deposit_context(
                    tenant=tenant,
                    tenancy=tenancy,
                    ledger_account=ledger_account,
                    amount=amount,
                )
            )

        messages.success(
            request,
            (
                f"Deposit of {result['amount']} created successfully. "
                f"Reference: {result['deposit_reference']}"
            )
        )

        return redirect(
            "finance:tenant_deposit",
            tenant_id=tenant.id
        )

    return render(
        request,
        "deposits/create_deposit.html",
        get_deposit_context(
            tenant=tenant,
            tenancy=tenancy,
            ledger_account=ledger_account,
        )
    )


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