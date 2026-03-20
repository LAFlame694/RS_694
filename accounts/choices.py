from django.db import models

class Role(models.TextChoices):
    LANDLORD = "LANDLORD", "Landlord"
    CARETAKER = "CARETAKER", "Caretaker"
    SYSTEM_ADMIN = "SYSTEM_ADMIN", "System Admin"
    SYSTEM = "SYSTEM", "System"