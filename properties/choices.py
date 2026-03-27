from django.db import models

class UnitType(models.TextChoices):
    BEDSITTER = "BEDSITTER", "Bedsitter"
    ONE_BEDROOM = "ONE_BEDROOM", "One Bedroom"
    TWO_BEDROOM = "TWO_BEDROOM", "Two Bedroom"
    SHOP = "SHOP", "Shop"

class UnitStatus(models.TextChoices):
    VACCANT = "VACCANT", "Vaccant"
    OCCUPIED = "OCCUPIED", "Occupied"
    MAINTENANCE = "MAINTENANCE", "Maintenance"