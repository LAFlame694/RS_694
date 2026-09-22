from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib import messages

from finance.models import Payment
from tenants.models import Tenant
from tenants.choices import TenancyStatus
from finance.services.deposits import get_deposit_dashboard, create_deposit_allocation
from finance.services.tenant_access import get_accessible_tenants

@login_required
def create_deposit_view(request, tenant_id):

    tenant = get_object_or_404(
        get_accessible_tenants(request.user),
        id=tenant_id
    )

    # get the tenant's active tenancy and ledger account
    tenancy = get_object_or_404(
        tenant.tenancies.select_related("ledger_account"),
        status=TenancyStatus.ACTIVE
    )

    ledger_account = tenancy.ledger_account

    # handle post
    if request.method == "POST":
        payment_id = request.POST.get("payment_id")
        amount = request.POST("amount")

        # validate payment
        payment = get_object_or_404(
            Payment,
            id=payment_id,
            ledger_account=ledger_account
        )

        try:
            # create deposit deposit allocation through service
            create_deposit_allocation(
                ledger_account=ledger_account,
                payment=payment,
                amount=amount,
                created_by=request.user,
            )

            messages.success(
                request, 
                "Deposit created successfully."
            )

            return redirect(
                "finance:tenant_deposit",
                tenant_id=tenant.id
            )

        except ValidationError as e:
            messages.error(
                request,
                str(e)
            )

        except Exception:
            messages.error(
                request,
                "Unable to create the deposit. Please try again."
            )

    payments = Payment.objects.filter(
        ledger_account=ledger_account
    ).order_by(
        "-payment_date",
        "-created_at"
    )

    context = {
        "tenant": tenant,
        "ledger_account": ledger_account,
        "payments": payments
    }

    return render(
        request,
        "deposits/create_deposit.html",
        context
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