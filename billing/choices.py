from django.db import models

class MeterReadingStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    BILLED = "BILLED", "Billed"

class InvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ISSUED = "ISSUED", "Issued"
    PARTIAL = "PARTIAL", "Partially Paid"
    PAID = "PAID", "Paid"
    OVERDUE = "OVERDUE", "Overdue"
    CANCELLED = "CANCELLED", "Cancelled"

class InvoiceCategory(models.TextChoices):
    RENT = "RENT", "Rent"   
    WATER = "WATER", "Water"
    ELECTRICITY = "ELECTRICITY", "Electricity"
    GARBAGE = "GARBAGE", "Garbage"
    PENALTY = "PENALTY", "Penalty"
    OTHER = "OTHER", "Other"

class ReccuringChargeCategory(models.TextChoices):
    WATER = "WATER", "Water"
    ELECTRICITY = "ELECTRICITY", "Electricity"
    GARBAGE = "GARBAGE", "Garbage"
    PARKING = "PARKING", "Parking Fee"
    SECURITY = "SECURITY", "Security Fee"
    OTHER = "OTHER", "Other"