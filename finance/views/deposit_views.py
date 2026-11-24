from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib import messages
from django.db.models import F

from tenants.models import Tenant, Tenancy
from tenants.choices import TenancyStatus

from billing.models import Invoice
from billing.choices import InvoiceStatus, InvoicePaymentStatus

from finance.services.deposits import (
    get_deposit_dashboard, 
    create_deposit_allocation,
    get_available_deposit,
    apply_deposit_to_invoice
)
from finance.services.tenant_access import get_accessible_tenants
from finance.services.credit_service import get_available_credit

import logging

logger = logging.getLogger(__name__)

# Create your views here

@login_required
def apply_deposit_view(request, tenant_id):

    """
    Apply available deposit funds to an outstanding invoice
    belonging to the selected tenant's ledger account.
    """

    # Retrieve tenant 
    accessible_tenants = get_accessible_tenants(
        request.user
    )

    tenant = get_object_or_404(
        accessible_tenants,
        pk=tenant_id,
    )

    # Retrieve the tenant's active tenancy.
    tenancy = get_object_or_404(
        Tenancy.objects.select_related(
            "ledger_account",
            "unit",
            "unit__property",
        ),
        tenant=tenant,
        status=TenancyStatus.ACTIVE,
    )

    ledger_account = tenancy.ledger_account

    # Calculate the tenant's financial balances.
    available_deposit = get_available_deposit(
        ledger_account
    )

    available_credit = get_available_credit(
        ledger_account
    )

    # Retrieve eligible outstanding invoices.
    invoices = (
        Invoice.objects
        .filter(
            ledger_account=ledger_account,
            status=InvoiceStatus.ISSUED,
            total_amount__gt=F("amount_paid"),
        )
        .order_by("due_date", "issue_date")
    )

    # Determine which invoice the user selected.
    selected_invoice_id = (
        request.POST.get("invoice_id")
        if request.method == "POST"
        else request.GET.get("invoice")
    )

    selected_invoice = None
    amount = ""

    if selected_invoice_id:
        selected_invoice = get_object_or_404(
            invoices,
            pk=selected_invoice_id,
        )

    # Process deposit application.
    if request.method == "POST":
        amount = request.POST.get("amount", "").strip()

        if not selected_invoice:
            messages.error(
                request,
                "Please select an invoice."
            )
        else:
            try:
                amount_applied = apply_deposit_to_invoice(
                    ledger_account=ledger_account,
                    invoice=selected_invoice,
                    amount=amount,
                    created_by=request.user,
                )

            except ValidationError as exc:
                messages.error(
                    request,
                    (
                        exc.message
                        if hasattr(exc, "message")
                        else str(exc)
                    )
                )

            except Exception:
                logger.exception(
                    "Unexpected error while applying deposit | "
                    "tenant_id=%s | invoice_id=%s | ledger_account_id=%s",
                    tenant.id,
                    selected_invoice.id,
                    ledger_account.id,
                )

                messages.error(
                    request,
                    "An unexpected error occurred while applying the deposit."
                )

            else:
                messages.success(
                    request,
                    (
                        f"Deposit of KSh {amount_applied:,.2f} "
                        f"successfully applied to invoice "
                        f"{selected_invoice.invoice_number}."
                    )
                )

                return redirect(
                    "finance:tenant_deposit",
                    tenant_id=tenant.id,
                )

    # Prepare page context.
    context = {
        "tenant": tenant,
        "tenancy": tenancy,
        "ledger_account": ledger_account,
        "available_deposit": available_deposit,
        "available_credit": available_credit,
        "invoices": invoices,
        "selected_invoice": selected_invoice,
        "amount": amount,
    }

    return render(
        request,
        "deposits/apply_deposits.html",
        context,
    )


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