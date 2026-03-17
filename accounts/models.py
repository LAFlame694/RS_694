from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from .choices import Role

# Create your models here.
class User(AbstractUser):
    role = models.CharField(
        max_length=20, 
        choices=Role.choices,
        default=Role.SYSTEM_ADMIN
    )
    phone_number = models.CharField(max_length=20, blank=True)
    landlord = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        limit_choices_to={"role": "LANDLORD"},
        related_name="caretakers"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.role == Role.CARETAKER and not self.landlord:
            raise ValidationError("Caretaker must be assigned to a landlord!")
        
        if self.role == Role.LANDLORD and self.landlord:
            raise ValidationError("Landlord cannot have a landlord assigned")
        
        if self.role == Role.SYSTEM_ADMIN and self.landlord:
            raise ValidationError("System admin cannot have a landlord assigned")
        
        if self.landlord and self.landlord.role != Role.LANDLORD:
            raise ValidationError("Landlord must have landlord role")
        
        super().clean()
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.username} ({self.role})"