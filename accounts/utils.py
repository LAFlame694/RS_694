from django.contrib.auth import get_user_model

User = get_user_model()

def get_system_user():
    user, _ = User.objects.get_or_create(
        username="System",
        defaults={
            "role": "SYSTEM",
            "is_active": False,
        }
    )

    return user

def is_landlord(user):
    return user.role == 'LANDLORD'

def is_caretaker(user):
    return user.role == 'CARETAKER'