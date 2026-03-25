from django.db import models

class LedgerEntryCategory(models.TextChoices):
    RENT = "RENT", "Rent"
    WATER = "WATER", "Water"
    ELECTRICITY = "ELECTRICITY", "Electricity"
    GARBAGE = "GARBAGE", "Garbage"
    DEPOSIT = "DEPOSIT", "Deposit"
    PENALTY = "PENALTY", "Penalty"
    OTHER = "OTHER", "Other"
    PAYMENT = "PAYMENT", "Payment"

class LedgerEntryType(models.TextChoices):
    CHARGE = "CHARGE", "Charge"
    PAYMENT = "PAYMENT", "Payment"
    ADJUSTMENT = "ADJUSTMENT", "Adjustment"
    REVERSAL = "REVERSAL", "Reversal"
    CREDIT = "CREDIT", "Credit"

class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    BANK = "BANK", "Bank"
    MPESA = "MPESA", "M-Pesa"
    CARD = "CARD", "Card"
    CHEQUE = "CHEQUE", "Cheque"
    OTHER = "OTHER", "Other"