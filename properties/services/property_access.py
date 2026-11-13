from properties.models import Property
from accounts.choices import Role

def get_accessible_properties(user):
    """
    Return properties accessible to the given user.
    """

    if user.role == Role.SYSTEM_ADMIN:
        properties = Property.objects.all()
    
    elif user.role == Role.LANDLORD:
        properties = Property.objects.filter(landlord=user)
    
    elif user.role == Role.CARETAKER:
        properties = Property.objects.filter(landlord=user.landlord)

    else:
        return Property.objects.none()
    
    return properties.distinct()