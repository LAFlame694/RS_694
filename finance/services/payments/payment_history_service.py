from django.db.models import Q
from django.shortcuts import get_object_or_404

from tenants.models import Tenant, Tenancy
from accounts.choices import Role
from finance.models import (
    Payment, 
    LedgerEntry, 
    DepositAllocation, 
    CreditAllocation,
    PaymentAllocation,
)

import logging

logger = logging.getLogger(__name__)

def get_payment_allocations(*, user, payment_id):

    payment = get_object_or_404(
        Payment.objects.select_related("ledger_account"),
        id=payment_id
    )

    if user.role == Role.LANDLORD:

        tenant = payment.ledger_account.tenancy.tenant

        if tenant.landlord_id != user.id:
            raise PermissionError(
                "You do not have permission "
                "to view allocations."
            )

    elif user.role != Role.SYSTEM_ADMIN:
        raise PermissionError(
            "You do not have permission "
            "to view allocations."
        )
    
    payment_allocations = PaymentAllocation.objects.filter(
        payment=payment
    ).select_related("invoice")

    credit_allocations = CreditAllocation.objects.filter(
        payment=payment
    ).select_related("invoice")

    return {
        "payment": payment,
        "payment_allocations": payment_allocations,
        "credit_allocations": credit_allocations,
    }

def get_payment_detail(*, user, payment_id):

    payment = get_object_or_404(
        Payment.objects.select_related(
            "ledger_account",
            "created_by"
        ),
        id=payment_id
    )

    if user.role == Role.LANDLORD:

        tenant = payment.ledger_account.tenancy.tenant

        if tenant.landlord_id != user.id:
            raise PermissionError(
                "You do not have permission "
                "to view this payment."
            )

    elif user.role != Role.SYSTEM_ADMIN:
        raise PermissionError(
            "You do not have permission "
            "to view this payment."
        )
    
    ledger_entries = LedgerEntry.objects.filter(
        payment=payment
    ).order_by("-created_at")

    deposit_allocations = DepositAllocation.objects.filter(
        payment=payment
    )

    return {
        "payment": payment,
        "ledger_entries": ledger_entries,
        "deposit_allocations": deposit_allocations,
    }

def get_tenant_payment_history(*, user, tenant_id):

    if user.role == Role.SYSTEM_ADMIN:
        # system admin sees all tenants
        tenant = get_object_or_404(Tenant, id=tenant_id)
    
    elif user.role == Role.LANDLORD:
        tenant = get_object_or_404(Tenant, id=tenant_id, landlord=user)
    
    elif user.role == Role.CARETAKER:
        tenant = get_object_or_404(Tenant, id=tenant_id, landlord=user.landlord)
    
    else:
        return Tenant.objects.none()
    
    try:
        tenancy = Tenancy.objects.select_related(
            "ledger_account"
        ).get(
            tenant=tenant
        )
    
    except Tenancy.DoesNotExist:

        return {
            "tenant": tenant,
            "payments": [],
            "ledger_account": None,
        }
    
    payments = Payment.objects.filter(
        ledger_account=tenancy.ledger_account
    ).order_by("-payment_date", "-created_at")

    logger.info(
        f"Payment history loaded | "
        f"user={user.id} | "
        f"tenant={tenant.id}"
    )

    return {
        "tenant": tenant,
        "payments": payments,
        "ledger_account": tenancy.ledger_account,
    }

def get_accessible_tenants(user, query=None):

    if user.role == Role.SYSTEM_ADMIN:
        # system admin sees all tenants
        tenants = Tenant.objects.all()
    
    elif user.role == Role.LANDLORD:
        tenants = Tenant.objects.filter(landlord=user)
    
    elif user.role == Role.CARETAKER:
        tenants = Tenant.objects.filter(landlord=user.landlord)
    
    else:
        return Tenant.objects.none()
    
    if query:
        tenants = tenants.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(id_number__icontains=query)
        ).distinct()

    logger.info(
        f"Tenant search | "
        f"user={user.id} | "
        f"role={user.role} | "
        f"query={query}"
    )

    return tenants.distinct()