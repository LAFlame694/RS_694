from properties.models import Property
from accounts.choices import Role

def get_accessible_properties(user):
    """
    Return properties accessible to the given user.
    """

    if user.role == Role.SYSTEM_ADMIN:
        properties = Property.objects.all()
    
    if user.role == Role.LANDLORD:
        properties = Property.objects.filter(landlord=user)
    
    if user.role == Role.CARETAKER:
        properties = Property.objects.filter(landlord=user.landlord)
    
    return properties.distinct()