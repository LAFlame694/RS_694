from django.db import models

class PaymentStatus(models.TextChoices):
    COMPLETED = "COMPLETED", "Completed"
    REVERSED = "REVERSED", "Reversed"

# business meaning choices
class LedgerEntryCategory(models.TextChoices):
    RENT = "RENT", "Rent"
    WATER = "WATER", "Water"
    ELECTRICITY = "ELECTRICITY", "Electricity"
    GARBAGE = "GARBAGE", "Garbage"
    SECURITY = "SECURITY", "Security Fee"
    PARKING = "PARKING", "Parking Fee"
    DEPOSIT = "DEPOSIT_ALLOCATION", "Deposit Allocation"
    LIABILITY = "DEPOSIT_LIABILITY", "Deposit Liability"
    PENALTY = "PENALTY", "Penalty"
    OTHER = "OTHER", "Other"
    PAYMENT = "PAYMENT", "Payment"
    REVERSAL = "REVERSAL", "Reversal"
    REFUND = "REFUND", "Refund"

# direction of money flow
class LedgerEntryType(models.TextChoices):
    CHARGE = "CHARGE", "Charge"
    CREDIT = "CREDIT", "Credit"

class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    BANK = "BANK", "Bank"
    MPESA = "MPESA", "M-Pesa"
    CARD = "CARD", "Card"
    CHEQUE = "CHEQUE", "Cheque"
    OTHER = "OTHER", "Other"

class SourceChoices(models.TextChoices):
    NORMAL = "NORMAL", "Normal Credit"
    DEPOSIT = "DEPOSIT", "Deposit"