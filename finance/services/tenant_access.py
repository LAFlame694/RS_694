from django.shortcuts import get_object_or_404

from django.db.models import Q
from accounts.choices import Role
from tenants.models import Tenant

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

    return tenants.distinct()

def get_accessible_tenant(*, user, tenant_id):
    """
    return a tenant only if the requesting user has acess to it.

    Access rules are inherited from get_accessible_tenants().
    """

    tenants = get_accessible_tenants(
        user=user
    )

    return get_object_or_404(
        tenants,
        id=tenant_id
    )