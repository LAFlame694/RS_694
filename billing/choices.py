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