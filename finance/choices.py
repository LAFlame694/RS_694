from django.db import models

class LedgerEntryCategory(models.TextChoices):
    RENT = "RENT", "Rent"
    WATER = "WATER", "Water"
    ELECTRICITY = "ELECTRICITY", "Electricity"
    DEPOSIT = "DEPOSIT", "Deposit"
    PENALTY = "PENALTY", "Penalty"
    OTHER = "OTHER", "Other"

class LedgerEntryType(models.TextChoices):
    CHARGE = "CHARGE", "Charge"
    PAYMENT = "PAYMENT", "Payment"
    ADJUSTMENT = "ADJUSTMENT", "Adjustment"
    REVERSAL = "REVERSAL", "Reversal"

class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    BANK = "BANK", "Bank"
    MPESA = "MPESA", "M-Pesa"
    CARD = "CARD", "Card"
    CHEQUE = "CHEQUE", "Cheque"
    OTHER = "OTHER", "Other"