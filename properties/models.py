from random import choices
from django.db import models
from django.conf import settings
from django.db.models import UniqueConstraint
from properties.choices import UnitType, UnitStatus

# Create your models here.
class Property(models.Model):
    landlord = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="properties",
        limit_choices_to={"role": "LANDLORD"}
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    address_line_1 = models.CharField(max_length=250)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    county = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["landlord", "name"],
                name="unique_property_name_per_landlord"
            )
        ]

        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.name} ({self.landlord.username})"

class Unit(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="units"
    )
    unit_number = models.CharField(max_length=20)
    unit_type = models.CharField(
        max_length=50,
        choices=UnitType.choices
    )
    status = models.CharField(
        max_length=50,
        choices=UnitStatus.choices,
        default=UnitStatus.VACCANT
    )
    floor = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["property", "unit_number"],
                name="unique_unit_number_per_property"
            )
        ]

        ordering = ["unit_number"]
    
    def __str__(self):
        return f"{self.property.name} - {self.unit_number} - {self.unit_type}"