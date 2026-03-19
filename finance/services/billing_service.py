from datetime import date
import calendar

from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from tenants.models import Tenancy
from finance.models import LedgerAccount, LedgerEntry
from finance.choices import LedgerEntryType, LedgerEntryCategory
from billing.models import Invoice, RecurringCharge

def generate_monthly_billing():
    """ 
    Main billing entry point.
    Called by cron command
    """

    today = timezone.now().date()

    generate_rent_invoices(today)
    generate_recurring_charge_invoices(today)

def get_billing_period(today):
    """
    Returns first and last day of the current month.
    """
    start = today.replace(day=1)

    last_day = calendar.monthrange(today.year, today.month)[1]
    end = today.replace(day=last_day)

    return start, end

def generate_rent_invoices(today):

    # get current billing window
    billing_start, billing_end = get_billing_period(today)

    active_tenancies = Tenancy.objects.filter(
        status="ACTIVE",
        start_date__lte=today
    ).select_related("tenant", "unit")

    for tenancy in active_tenancies:
        ledger_account = tenancy.ledger_account

        invoice_exists = Invoice.objects.filter(
            ledger_account=ledger_account,
            category=LedgerEntryCategory.RENT,
            billing_period_start=billing_start,
            billing_period_end=billing_end
        ).exists()

        if invoice_exists:
            continue

        create_invoice_and_ledger_entry(
            tenancy=tenancy,
            ledger_account=ledger_account,
            category=LedgerEntryCategory.RENT,
            amount=tenancy.rent_amount,
            billing_start=billing_start,
            billing_end=billing_end,
            today=today
        )

def generate_recurring_charge_invoices(today):
    billing_start, billing_end = get_billing_period(today)

    charges = RecurringCharge.objects.filter(
        is_active=True,
        start_date__lte=today
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    )

    for charge in charges:

        # run only on correct day
        if charge.day_of_month and charge.day_of_month != today.day:
            continue

        unit_types = [
            ut.strip() for ut in charge.applies_to_unit_types.split(",")
        ]

        # get eligible tenancies based on UnitType
        tenancies = Tenancy.objects.filter(
            status="ACTIVE",
            start_date__lte=today,
            unit__property=charge.property,
            unit__unit_type__in=unit_types
        ).select_related("unit", "tenant")

        for tenancy in tenancies:
            ledger_account = tenancy.ledger_account

            # prevent duplicate invoices
            invoice_exists = Invoice.objects.filter(
                ledger_account=ledger_account,
                category=charge.category,
                billing_period_start=billing_start,
                billing_period_end=billing_end
            ).exists()

            if invoice_exists:
                continue

            create_invoice_and_ledger_entry(
                tenancy=tenancy,
                ledger_account=ledger_account,
                category=charge.category,
                amount=charge.amount,
                billing_start=billing_start,
                billing_end=billing_end,
                today=today
            )
        
        # track last generation
        charge.last_generated_date = today
        charge.save(update_fields=["last_generated_date"])

def create_invoice_and_ledger_entry(
        tenancy,
        ledger_account,
        category,
        amount,
        billing_start,
        billing_end,
        today
):
    
    with transaction.atomic():
        invoice = Invoice.objects.create(
            tenancy=tenancy,
            ledger_account=ledger_account,
            category=category,
            issue_date=today,
            due_date=billing_end,
            billing_period_start=billing_start,
            billing_period_end=billing_end,
            total_amount=amount,
            status=Invoice.Status.ISSUED,
            created_by=tenancy.created_by
        )

        LedgerEntry.objects.create(
            ledger_account=ledger_account,
            invoice=invoice,
            entry_type=LedgerEntryType.CHARGE,
            category=category,
            amount=amount,
            entry_date=today,
            description=f"{category} charge for {billing_start} - {billing_end}",
            created_by=tenancy.created_by
        )