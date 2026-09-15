from decimal import Decimal
from django.db.models import Sum
from django.db import transaction
from django.utils import timezone

from billing.models import Invoice
from billing.choices import InvoiceStatus
from finance.models import LedgerEntry
from finance.choices import SourceChoices, LedgerEntryType, LedgerEntryCategory

import logging

logger = logging.getLogger("credit")

def get_available_credit(ledger_account):

    credits = LedgerEntry.objects.filter(
        ledger_account=ledger_account,
        entry_type=LedgerEntryType.CREDIT,
        source=SourceChoices.NORMAL,
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    normal_charges = LedgerEntry.objects.filter(
        ledger_account=ledger_account,
        entry_type=LedgerEntryType.CHARGE,
        source=SourceChoices.NORMAL,
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    available = credits - normal_charges

    return max(available, Decimal("0.00"))

@transaction.atomic
def apply_available_credit_to_invoices(
    *, ledger_account, created_by, entry_date=None,
):

    if entry_date is None:
        entry_date = timezone.now().date()

    available_credit = get_available_credit(ledger_account)

    if available_credit <= Decimal("0.00"):
        logger.info(
            "No available credit to apply | ledger=%s",
            ledger_account.id
        )

        return Decimal("0.00")

    invoices = Invoice.objects.select_for_update().filter(
        ledger_account=ledger_account,
        status__in=[
            InvoiceStatus.ISSUED,
            InvoiceStatus.PARTIAL
        ],
    ).order_by(
        "issue_date",
        "id",
    )

    total_applied = Decimal("0.00")

    for invoice in invoices:

        if available_credit <= Decimal("0.00"):
            break

        outstanding = invoice.outstanding_balance

        if outstanding <= Decimal("0.00"):
            continue

        amount_to_apply = min(
            available_credit, outstanding
        )

        # create the financial transaction
        LedgerEntry.objects.create(
            ledger_account=ledger_account,
            invoice=invoice,
            source=SourceChoices.NORMAL,
            entry_type=LedgerEntryType.CHARGE,
            category=invoice.category,
            amount=amount_to_apply,
            entry_date=entry_date,
            description=(
                f"Normal credit applied to invoice "
                f"{invoice.invoice_number}"
            ),
            created_by=created_by
        )

        # update cached invoice payment information
        invoice.amount_paid += amount_to_apply

        if invoice.amount_paid >= invoice.total_amount:
            invoice.amount_paid = invoice.total_amount
            invoice.status = InvoiceStatus.PAID
        else:
            invoice.status = InvoiceStatus.PARTIAL

        invoice.save(
            update_fields=[
                "amount_paid", "status",
            ]
        )

        available_credit -= amount_to_apply
        total_applied += amount_to_apply

        logger.info(
            "Available credit applied | ledger=%s | invoice=%s | "
            "amount=%s | remaining_credit=%s",
            ledger_account.id,
            invoice.invoice_number,
            amount_to_apply,
            available_credit,
        )

    logger.info(
        "Available credit application complete | ledger=%s | "
        "total_applied=%s | remaining_credit=%s",
        ledger_account.id,
        total_applied,
        available_credit,
    )

    return total_applied