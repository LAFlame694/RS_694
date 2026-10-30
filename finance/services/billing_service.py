import calendar

from django.utils import timezone
from django.db.models import Q
import logging

from tenants.models import Tenancy
from finance.choices import LedgerEntryCategory
from billing.models import Invoice, RecurringCharge
from billing.choices import InvoiceStatus
from billing.services.invoice_services import create_invoice_service
from accounts.utils import get_system_user

logger = logging.getLogger("billing")

def generate_monthly_billing():
    """
    Main billing entry point.
    Called by cron command
    """

    logger.info("=== Monthly billing job STARTED ===")

    system_user = get_system_user()
    today = timezone.now().date()

    logger.info(f"Billing date: {today}")

    generate_rent_invoices(today, system_user)
    generate_recurring_charge_invoices(today, system_user)

    logger.info("=== Monthly billing job COMPLETED ===")

def get_billing_period(today):
    """
    Returns first and last day of the current month.
    """
    start = today.replace(day=1)

    last_day = calendar.monthrange(today.year, today.month)[1]
    end = today.replace(day=last_day)

    return start, end

def generate_rent_invoices(today, system_user):

    # get current billing window
    billing_start, billing_end = get_billing_period(today)
    logger.info(f"Generating RENT invoices for period {billing_start} to {billing_end}")

    active_tenancies = Tenancy.objects.filter(
        status="ACTIVE",
        start_date__lte=today
    ).select_related("tenant", "unit")
    logger.info(f"Found {active_tenancies.count()} active tenancies for rent billing")

    if not active_tenancies.exists():
        logger.warning("No active tenancies found for rent billing")
        return

    for tenancy in active_tenancies:
        ledger_account = tenancy.ledger_account

        invoice_exists = Invoice.objects.filter(
            ledger_account=ledger_account,
            category=LedgerEntryCategory.RENT,
            billing_period_start=billing_start,
            billing_period_end=billing_end
        ).exists()

        if invoice_exists:
            logger.info(
                f"Invoice already exists for tenancy {tenancy.id}, category RENT"
            )
            continue

        logger.info(
            f"Creating RENT invoice | tenancy={tenancy.id} | amount={tenancy.rent_amount}"
        )

        create_invoice_service(
            tenancy=tenancy,
            category=LedgerEntryCategory.RENT,
            amount=tenancy.rent_amount,
            issue_date=today,
            due_date=billing_end,
            billing_period_start=billing_start,
            billing_period_end=billing_end,
            created_by=system_user,
            status=InvoiceStatus.ISSUED,
        )

def generate_recurring_charge_invoices(today, system_user):
    billing_start, billing_end = get_billing_period(today)

    logger.info("Starting recurring charge billing")

    charges = RecurringCharge.objects.filter(
        is_active=True,
        start_date__lte=today
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    )
    logger.info(f"Found {charges.count()} active recurring charges")

    if not charges.exists():
        logger.warning("No recurring charges found")
        return

    for charge in charges:
        logger.info(
            f"Processing charge {charge.id} | property={charge.property.id} | amount={charge.amount}"
        )
        
        if charge.day_of_month and today.day < charge.day_of_month:
            logger.info(
                f"Skipping charge {charge.id} - waiting for billing day {charge.day_of_month}"
            )
            continue

        unit_types = charge.applies_to_unit_types

        # get eligible tenancies based on UnitType
        tenancies = Tenancy.objects.filter(
            status="ACTIVE",
            start_date__lte=today,
            unit__property=charge.property,
            unit__unit_type__in=unit_types
        ).select_related("unit", "tenant")
        logger.info(
            f"{tenancies.count()} tenancies eligible for charge {charge.id}"
        )

        if not tenancies.exists():
            logger.warning(f"No eligible tenancies for charge {charge.id}")
            continue

        invoices_created = False

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
                logger.info(
                    f"Invoice exists | tenancy={tenancy.id} | charge={charge.id}"
                )
                continue

            logger.info(
                f"Creating charge invoice | tenancy={tenancy.id} | charge={charge.id} | amount={charge.amount}"
            )

            create_invoice_service(
                tenancy=tenancy,
                category=LedgerEntryCategory.RENT,
                amount=tenancy.rent_amount,
                issue_date=today,
                due_date=billing_end,
                billing_period_start=billing_start,
                billing_period_end=billing_end,
                created_by=system_user,
                status=InvoiceStatus.ISSUED,
            )

            invoices_created = True
        
        # track last generation
        if invoices_created:
            logger.info(
                f"Charge {charge.id} processed successfully"
            )
            charge.last_generated_date = today
            charge.save(update_fields=["last_generated_date"])
        else:
            logger.warning(
                f"No invoices created for charge {charge.id} - last_generated_date not updated"
            )