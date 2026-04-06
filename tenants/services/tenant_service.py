from django.db.models import OuterRef, Subquery, Exists
from tenants.models import Tenancy, Tenant
from accounts.choices import Role

# create your services here.
def get_tenants_for_user(user):
    """
    Return tenants scoped to the current user
    """

    if user.role == Role.SYSTEM_ADMIN:
        # system admin sees all tenants
        tenants = Tenant.objects.all()
    
    elif user.role == Role.LANDLORD:
        tenants = Tenant.objects.filter(landlord=user)
    
    elif user.role == Role.CARETAKER:
        tenants = Tenant.objects.filter(landlord=user.landlord)
    
    else:
        return Tenant.objects.none()
    
    active_tenancy = Tenancy.objects.filter(
        tenant=OuterRef("pk"),
        end_date__isnull=True
    )

    # annotate
    tenants = tenants.annotate(
        has_active_tenancy=Exists(active_tenancy),
        current_unit_name=Subquery(
            active_tenancy.values("unit__unit_number")[:1]
        ),
        current_property_name=Subquery(
            active_tenancy.values("unit__property__name")[:1]
        )
    )

    return tenants.order_by("-id")