from django.db.models import OuterRef, Subquery, Exists, Q, Value
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.db.models.functions import Concat

from tenants.models import Tenancy, Tenant
from accounts.choices import Role

# create your services here.
@transaction.atomic
def update_tenant(tenant: Tenant, data: dict) -> Tenant:
    # validate id number
    id_number = data.get("id_number")

    if id_number:
        exists = Tenant.objects.exclude(id=tenant.id).filter(id_number=id_number).exists()
        if exists:
            raise ValidationError("A tenant with this ID number already exists.")
        
        # update fields
        tenant.first_name = data.get("first_name", tenant.first_name)
        tenant.last_name = data.get("last_name", tenant.last_name)
        tenant.phone_number = data.get("phone_number", tenant.phone_number)
        tenant.email = data.get("email", tenant.email)
        tenant.id_number = data.get("id_number", tenant.id_number)

        tenant.save()

        return tenant

def create_tenant(
        *,
        first_name,
        last_name,
        phone_number,
        email,
        id_number,
        created_by,
        landlord=None
):
    """
    creates a tenant with proper landlord assignment.
    """

    # resolve landlord
    if created_by.role == Role.SYSTEM_ADMIN:
        if not landlord:
            raise ValidationError("Landlord must be provided.")
    
    elif created_by.role == Role.LANDLORD:
        landlord = created_by
    
    elif created_by.role == Role.CARETAKER:
        landlord = created_by.landlord
    
    else:
        raise ValidationError("Invalid user role.")
    
    # prevent duplicate phone and ID per landlord
    if Tenant.objects.filter(
        landlord=landlord
    ).filter(
        Q(phone_number=phone_number) | Q(id_number=id_number)
    ).exists():
        raise ValidationError("Tenant with this phone number or ID already exists.")
    
    # create tenant
    try:
        tenant = Tenant.objects.create(
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            email=email,
            id_number=id_number,
            landlord=landlord,
            created_by=created_by
        )
    except IntegrityError:
        raise ValidationError("Tenant with this phone number or ID already exists.")

    return tenant

def get_tenants_for_user(user, search_query=None, status=None):
    """
    Return tenants scoped to the current user
    + optional search filtering
    + optional status filter
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
    
    # search logic
    if search_query:
        tenants = tenants.annotate(
            full_name=Concat("first_name", Value(" "), "last_name")
        ).filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(phone_number__icontains=search_query) |
            Q(full_name__icontains=search_query)
        )
    
    # find active tenant for this tenant
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

    # filter by status
    if status == "active":
        tenants = tenants.filter(has_active_tenancy=True)
    
    elif status == "inactive":
        tenants = tenants.filter(has_active_tenancy=False)

    return tenants.order_by("-id").distinct()