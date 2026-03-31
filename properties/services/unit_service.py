from django.db.models import Prefetch
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction

from tenants.models import Tenancy, Tenant
from properties.models import Unit, Property
from tenants.choices import TenancyStatus

@transaction.atomic
def assign_tenant_to_unit(unit: Unit, tenant: Tenant, created_by) -> Tenancy:
    """
    Assign a tenant to a unit.
    Creates a new tenancy and updates unit status.
    """

    # true source of truth check
    existing_active = unit.tenancies.filter(status=TenancyStatus.ACTIVE).exists()

    if existing_active:
        raise ValidationError(f"Unit {unit} is already occupied.")
    
    tenancy = Tenancy.objects.create(
        tenant=tenant,
        unit=unit,
        start_date=timezone.now().date(),
        rent_amount=getattr(unit, 'default_rent', 0), # fallback to 0 if not set
        status=TenancyStatus.ACTIVE,
        created_by=created_by
    )

    # sync unit status
    unit.status = 'OCCUPIED'
    unit.save(update_fields=['status'])

    return tenancy

@transaction.atomic
def vacate_unit(unit: Unit):
    """
    vacate the unit.
    Terminates active tenancy and updates unit status.
    """

    active_tenancy = unit.tenancies.filter(
        status=TenancyStatus.ACTIVE
    ).first()

    if not active_tenancy:
        raise ValidationError(f"Unit {unit} has no active tenancy.")
    
    # terminate tenancy
    active_tenancy.status = TenancyStatus.TERMINATED
    active_tenancy.end_date = timezone.now().date()
    active_tenancy.save(update_fields=['status', 'end_date'])

    # sync unit status
    unit.status = 'VACANT'
    unit.save(update_fields=['status'])

def get_property_with_units(user, property_id):
    """
    Ensures:
    - The property belongs to the user
    - Fetch related units
    """

    property = Property.objects.filter(
        id=property_id,
        landlord=user
    ).first()

    if not property:
        return None, None
    
    active_tenancies = Tenancy.objects.filter(
        status='ACTIVE'
    ).select_related('tenant')

    units = property.units.prefetch_related(
        Prefetch(
            'tenancies',
            queryset=active_tenancies,
            to_attr='active_tenancies'
        )
    ).order_by('unit_number')

    # attach single active tenancy
    for unit in units:
        unit.active_tenancy = (
            unit.active_tenancies[0] if unit.active_tenancies else None
        )

    return property, units

def get_units_stats(units):
    total_units = units.count()
    occupied = units.filter(status='OCCUPIED').count()
    vacant = units.filter(status='VACANT').count()
    maintenance = units.filter(status='MAINTENANCE').count()

    return {
        "total": total_units,
        "occupied": occupied,
        "vacant": vacant,
        "maintenance": maintenance,
    }