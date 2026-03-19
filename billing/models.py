from random import choice
from django.db import models, transaction
from tenants.models import Tenancy
from properties.models import Unit, Property
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from finance.choices import LedgerEntryCategory
from properties.choices import UnitType

# Create your models here.
class InvoiceSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.year} - {self.last_number}"

class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ISSUED = "ISSUED", "Issued"
        PARTIAL = "PARTIAL", "Partially Paid"
        PAID = "PAD", "Paid"
        OVERDUE = "OVERDUE", "Overdue"
        CANCELLED = "CANCELLED", "Cancelled"
    
    tenancy = models.ForeignKey(
        Tenancy,
        on_delete=models.PROTECT,
        related_name="invoices"
    )
    ledger_account = models.ForeignKey(
        "finance.LedgerAccount",
        on_delete=models.PROTECT,
        related_name="invoices"
    )
    category = models.CharField(
        max_length=20,
        choices=LedgerEntryCategory.choices
    )
    invoice_number = models.CharField(max_length=50, unique=True, blank=True)
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    billing_period_start = models.DateField(null=True, blank=True)
    billing_period_end = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )
    amount_paid = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_invoices"
    )

    class Meta:
        ordering = ["-issue_date"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "ledger_account",
                    "category",
                    "billing_period_start",
                    "billing_period_end"
                ],
                name="unique_invoice_per_charge_per_period"
            )
        ]
    
    # safe invoice generator
    def generate_invoice_number(self):
        year = timezone.now().year

        with transaction.atomic():
            sequence, created, = InvoiceSequence.objects.select_for_update().get_or_create(
                year=year
            )
            sequence.last_number += 1
            sequence.save()

            number = sequence.last_number

        return f"INV-{year}-{number:04d}"
    
    # auto generate when saving
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()

        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.tenancy}"

class Meter(models.Model):
    class MeterType(models.TextChoices):
        WATER = "WATER", "Water"
        ELECTRICITY = "ELECTRICITY", "Electricity"
        GAS = "GAS", "Gas"

    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="meters"
    )
    meter_type = models.CharField(max_length=20, choices=MeterType.choices)
    meter_number = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["meter_number"],
                name="unique_meter_number"
            )
        ]
        ordering = ["meter_type"]

    def __str__(self):
        return f"{self.unit} - {self.meter_type} ({self.meter_number})"

class MeterReading(models.Model):
    meter = models.ForeignKey(
        Meter,
        on_delete=models.PROTECT,
        related_name="readings"
    )
    reading_date = models.DateField()
    previous_reading = models.DecimalField(max_digits=12, decimal_places=3)
    current_reading = models.DecimalField(max_digits=12, decimal_places=3)
    consumption = models.DecimalField(
        max_digits=12, 
        decimal_places=3,
        editable=False
    )
    rate_per_unit = models.DecimalField(max_digits=20, decimal_places=3)
    amount = models.DecimalField(
        max_digits=20, 
        decimal_places=2,
        editable=False
    )
    is_billed = models.BooleanField(default=False)
    invoice = models.OneToOneField(
        Invoice,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="meter_reading"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_meter_readings"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["meter", "reading_date"],
                name="unique_meter_reading_per_day"
            )
        ]

        ordering = ["-reading_date"]
    
    def clean(self):
        if self.current_reading < self.previous_reading:
            raise ValidationError("Current reading cannot be less than previous reading")
        
        return super().clean()
    
    def save(self, *args, **kwargs):

        # Auto calculate consuption
        self.consumption = self.current_reading - self.previous_reading

        # auto calculate amount
        self.amount = self.consumption * self.rate_per_unit

        # run model validation
        self.full_clean()

        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.meter} - {self.reading_date}"
 
class RecurringCharge(models.Model):
    class Frequency(models.TextChoices):
        MONTHLY = "MONTHLY", "Monthly"

    applies_to_unit_types = models.CharField(
        max_length=255,
        help_text="Comma separated unit types"
    )
    category = models.CharField(
        choices=LedgerEntryCategory.choices,
        max_length=20
    )

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="recurring_charges"
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    frequency = models.CharField(
        max_length=20, 
        choices=Frequency.choices, 
        default=Frequency.MONTHLY
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    day_of_month = models.PositiveSmallIntegerField(
        help_text="Day of month to generate charge (1-31)"
    )
    last_generated_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Last Date this charge was generated"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_recurring_charges"
    )

    class Meta:
        ordering = ["-start_date"]
    
    def clean(self):
        valid_types = [choice[0] for choice in UnitType.choices]

        input_types = [
            ut.strip() for ut in self.applies_to_unit_types.split(",")
        ]

        for ut in input_types:
            if ut not in valid_types:
                raise ValidationError(f"{ut} is not a valid UnitType")

        # only validate if value is provided
        if self.day_of_month is not None:
            if self.day_of_month < 1 or self.day_of_month > 31:
                raise ValidationError("Day of month must be between 1 and 31.")
        
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")
        
        if self.category == LedgerEntryCategory.RENT:
            raise ValidationError("Rent should not be created as recurring charge")
        
        return super().clean()

    def __str__(self):
        return f"{self.category} - {self.amount}"