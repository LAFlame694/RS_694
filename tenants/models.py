from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from accounts.models import User
from django.db.models import UniqueConstraint
from properties.models import Unit

# Create your models here.
class Tenancy(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("ENDED", "Ended"),
        ("TERMINATED", "Terminated"),
    ]
    tenant = models.ForeignKey(
        "Tenant",
        on_delete=models.PROTECT,
        related_name="tenancies"
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="tenancies"
    )
    start_date = models.DateField() # when tenancy officially begins
    end_date = models.DateField(null=True, blank=True) # when tenancy ends
    rent_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ACTIVE"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tenancies"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]

        constraints = [
            models.UniqueConstraint(
                fields=["unit"],
                condition=Q(status="ACTIVE"),
                name="unique_active_tenancy_per_unit"
            )
        ]
    
    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")
        
    def __str__(self):
        return f"{self.tenant} - {self.unit} - {self.status}"

class Tenant(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    landlord = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        limit_choices_to={"role": "LANDLORD"},
        related_name="tenants"
    )
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    id_number = models.CharField(max_length=50)
    date_of_birth = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["id_number", "landlord"],
                name="unique_id_per_landlord"
            )
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"