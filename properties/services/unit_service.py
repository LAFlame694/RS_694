from django.db.models import Prefetch, Q
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db import IntegrityError

from tenants.models import Tenancy, Tenant
from properties.models import Unit, Property
from tenants.choices import TenancyStatus
from properties.choices import UnitStatus

@transaction.atomic
def create_unit(*, property, unit_number, unit_type, floor):
    """
    Create a new unit with enforced defaults.
    """
    try:
        unit = Unit.objects.create(
            property=property,
            unit_number=unit_number,
            unit_type=unit_type,
            floor=floor,

            # enforce business rules
            status=UnitStatus.VACANT,
            is_active=True
        )

        return unit
    except IntegrityError:
        raise ValidationError(
            f"Unit number '{unit_number}' already exists in property '{property}'."
        )

def get_unit_details(unit_id):
    """
    Fetch unit with all related tenancy data.
    Optimized for detail page.
    """

    unit = get_object_or_404(
        Unit.objects.select_related('property'),
        id=unit_id
    )

    tenancies = unit.tenancies.select_related('tenant').all()

    active_tenancy = None
    for tenancy in tenancies:
        if tenancy.status == TenancyStatus.ACTIVE:
            active_tenancy = tenancy
            break
    
    return {
        "unit": unit,
        "active_tenancy": active_tenancy,
        "tenancies": tenancies
    }

@transaction.atomic
def update_unit(unit, **data):
    """
    Update unit structural details only.
    """

    for field, value in data.items():
        setattr(unit, field, value)
    
    unit.save()
    return unit

@transaction.atomic
def delete_unit(unit: Unit):
    """
    Delete a unit safely.
    Only vacant units can be deleted.
    """

    # enforce business rule
    if unit.status in ['OCCUPIED', 'MAINTENANCE']:
        raise ValidationError(
            f"Cannot delete unit {unit}. Only vacant units can be deleted."
        )
    
    active_tenancy_exists = unit.tenancies.filter(
        status=TenancyStatus.ACTIVE
    ).exists()

    if active_tenancy_exists:
        raise ValidationError("Cannot delete unit with an active tenancy.")
    
    unit.delete()


@transaction.atomic
def assign_tenant_to_unit(unit: Unit, tenant: Tenant, rent_amount, start_date, created_by) -> Tenancy:
    """
    Assign a tenant to a unit.
    Creates a new tenancy and updates unit status.
    """

    # check if unit is already occupied
    if unit.tenancies.filter(status=TenancyStatus.ACTIVE).exists():
        raise ValidationError(f"Unit {unit} is already occupied.")
    
    # check if tenant has an active tenancy
    if tenant.tenancies.filter(status=TenancyStatus.ACTIVE).exists():
        raise ValidationError(f"Tenant {tenant} already has an active tenancy.")
    
    # create tenancy
    tenancy = Tenancy.objects.create(
        tenant=tenant,
        unit=unit,
        rent_amount=rent_amount,
        start_date=start_date,
        status=TenancyStatus.ACTIVE,
        created_by=created_by
    )

    # sync unit status
    unit.status = UnitStatus.OCCUPIED
    unit.save(update_fields=['status'])

    return tenancy

@transaction.atomic
def vacate_unit(unit: Unit):
    """
    vacate the unit.
    Terminates active tenancy and updates unit status.
    """

    active_tenancies = unit.tenancies.filter(
        status=TenancyStatus.ACTIVE
    )

    count = active_tenancies.count()

    if count == 0:
        raise ValidationError(f"Unit {unit} has no active tenancy.")
    
    if count > 1:
        raise ValidationError(
            f"Data integrity error: multiple active tenancies for unit {unit}."
        )
    
    active_tenancy = active_tenancies.first()

    # safety check
    if active_tenancy.start_date > timezone.now().date():
        raise ValidationError("Cannot vacate tenancy before it starts.")
    
    # idempotency protection
    if active_tenancy.status != TenancyStatus.ACTIVE:
        raise ValidationError("Tenancy already terminated.")

    # terminate tenancy
    active_tenancy.status = TenancyStatus.TERMINATED
    active_tenancy.end_date = timezone.now().date()
    active_tenancy.save(update_fields=['status', 'end_date'])

    # sync unit status
    unit.status = UnitStatus.VACANT
    unit.save(update_fields=['status'])

    return active_tenancy

def get_property_with_units(user, property_id, status=None, search=None):
    property = Property.objects.filter(
        id=property_id,
        landlord=user
    ).first()

    if not property:
        return None, None
    
    active_tenancies = Tenancy.objects.filter(
        status=TenancyStatus.ACTIVE
    ).select_related('tenant')

    units = property.units.all()

    # filter
    if status and status != 'ALL':
        units = units.filter(status=status)
    
    # search (unit number or tenant name)
    if search:
        units = units.filter(
            Q(unit_number__icontains=search) |
            (
                Q(tenancies__status=TenancyStatus.ACTIVE) &
                (
                    Q(tenancies__tenant__first_name__icontains=search) |
                    Q(tenancies__tenant__last_name__icontains=search)
                )
            )
    ).distinct()
    
    # prefetch (after filtering + search)
    units = units.prefetch_related(
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