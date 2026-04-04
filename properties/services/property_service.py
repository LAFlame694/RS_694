from properties.models import Property
from accounts.choices import Role

from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404

# create your sevices here
def get_property_details(*, user, property_id):
    """
    Fetch a single property for viewing.
    """

    property = get_object_or_404(
        Property.objects.select_related("landlord"),
        id=property_id
    )

    return property

@transaction.atomic
def update_property(*, user, property_id, **data):
    """
    Update property details.
    Landlord cannot be changed.
    """

    property = Property.objects.filter(
        id=property_id,
        landlord=user if user.role == Role.LANDLORD else None
    ).first()

    # fallback for caretaker/admin
    if not property:
        property = Property.objects.filter(id=property_id).first()
    
    if not property:
        raise ValidationError("Property not found.")
    
    # prevent landlord change
    if "landlord" in data:
        raise ValidationError("Landlord cannot be changed.")
    
    # update fields
    for field, value in data.items():
        setattr(property, field, value)
    
    property.save()
    return property

@transaction.atomic
def create_property(*, user, **data):
    """
    Create property with proper landlord assignment.
    """

    # determine landlord
    if user.role == Role.LANDLORD:
        landlord = user
    
    elif user.role == Role.CARETAKER:
        if not user.landlord:
            raise ValidationError("Caretaker is not linked to a landlord.")
        landlord = user.landlord
    
    elif user.role == Role.SYSTEM_ADMIN:
        landlord = data.get("landlord")
        if not landlord:
            raise ValidationError("Landlord must be provided.")
    
    else:
        raise ValidationError("Invalid user role.")
    
    try:
        property = Property.objects.create(
            landlord=landlord,
            name=data.get("name"),
            description=data.get("description"),
            address_line_1=data.get("address_line_1"),
            address_line_2=data.get("address_line_2"),
            country=data.get("country"),
            county=data.get("county"),
            postal_code=data.get("postal_code"),
            is_active=data.get("is_actiev", True),
        )

        return property
    
    except IntegrityError:
        raise ValidationError(
            "A property with this name already exists for this landlord."
        )

def get_properties_for_user(user):
    return Property.objects.filter(landlord=user).order_by('-created_at')

def get_property_stats(user):
    properties = Property.objects.filter(landlord=user)

    total_properties = properties.count()
    active_properties = properties.filter(is_active=True).count()
    inactive_properties = properties.filter(is_active=False).count()
    total_units = sum([p.units.count() for p in properties])

    return {
        "total": total_properties,
        "active": active_properties,
        "inactive": inactive_properties,
        "units": total_units,
    }