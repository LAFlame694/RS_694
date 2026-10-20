from django.db import models

class MeterReadingStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    BILLED = "BILLED", "Billed"

class InvoicePaymentStatus(models.TextChoices):
    UNPAID = "UNPAID", "Unpaid"
    PAID = "PAID", "Paid"
    PARTIAL = "PARTIAL", "Partially Paid"

class InvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ISSUED = "ISSUED", "Issued"
    CANCELLED = "CANCELLED", "Cancelled"

class InvoiceCategory(models.TextChoices):
    RENT = "RENT", "Rent"   
    WATER = "WATER", "Water"
    ELECTRICITY = "ELECTRICITY", "Electricity"
    GARBAGE = "GARBAGE", "Garbage"
    PENALTY = "PENALTY", "Penalty"
    OTHER = "OTHER", "Other"
    REFUND = "REFUND", "Refund"

class ReccuringChargeCategory(models.TextChoices):
    WATER = "WATER", "Water"
    ELECTRICITY = "ELECTRICITY", "Electricity"
    GARBAGE = "GARBAGE", "Garbage"
    PARKING = "PARKING", "Parking Fee"
    SECURITY = "SECURITY", "Security Fee"
    OTHER = "OTHER", "Other"