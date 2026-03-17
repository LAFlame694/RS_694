import uuid
from django.db import models
from tenants.models import Tenancy
from django.conf import settings
from .choices import LedgerEntryCategory, LedgerEntryType, PaymentMethod

# Create your models here.
class LedgerAccount(models.Model):
    tenancy = models.OneToOneField(
        Tenancy,
        on_delete=models.PROTECT,
        related_name="ledger_account"
    )
    account_number = models.CharField(max_length=30, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
    
    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number=self.generate_account_number()
        super().save(*args, **kwargs)

    def generate_account_number(self):
        return f"LA-{uuid.uuid4().hex[:10].upper()}"

    def __str__(self):
        return f"{self.account_number} - {self.tenancy}"

class LedgerEntry(models.Model):
    ledger_account = models.ForeignKey(
        LedgerAccount,
        on_delete=models.PROTECT,
        related_name="entries"
    )
    invoice = models.ForeignKey(
        "billing.Invoice",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ledger_entries"
    )
    entry_type = models.CharField(
        max_length=20,
        choices=LedgerEntryType.choices
    )
    category = models.CharField(
        max_length=30,
        choices=LedgerEntryCategory.choices
    )
    payment = models.OneToOneField(
        "Payment",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ledger_entry"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.TextField(blank=True)
    reference_code = models.CharField(max_length=50, unique=True, editable=False)
    related_entry = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversals"
    )
    entry_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_ledger_entries"
    )

    class Meta:
        ordering = ["-entry_date", "-created_at"]
    
    def save(self, *args, **kwargs):
        if not self.reference_code:
            self.reference_code = self.generate_reference_code()
        super().save(*args, **kwargs)
    
    def generate_reference_code(self):
        return f"LE-{uuid.uuid4().hex[:10].upper()}"

    def __str__(self):
        return f"{self.entry_type} - {self.category} - {self.amount}"

class Payment(models.Model):
    ledger_account = models.ForeignKey(
        LedgerAccount,
        on_delete=models.PROTECT,
        related_name="payments"
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    payment_date = models.DateField()

    method = models.CharField(
        max_length=20, 
        choices=PaymentMethod.choices
    )

    reference_code = models.CharField(
        max_length=100,
        unique=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    def save(self, *args, **kwargs):
        if not self.reference_code:
            self.reference_code = f"PAY-{uuid.uuid4().hex[:10].upper()}"
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.reference_code} - {self.amount}"