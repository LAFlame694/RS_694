from properties.models import Property

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