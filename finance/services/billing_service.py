import calendar
import logging

from django.db.models import Q
from django.utils import timezone

from tenants.models import Tenancy
from billing.models import Invoice, RecurringCharge
from billing.choices import InvoiceStatus, InvoiceCategory
from billing.services.invoice_services import create_invoice_service
from accounts.utils import get_system_user


logger = logging.getLogger("billing")


def generate_monthly_billing(*, properties=None):
    """
    Main monthly billing entry point.

    properties=None:
        Generate invoices for all properties.

    properties=queryset:
        Generate invoices only for the supplied properties.
    """

    logger.info("=== Monthly billing job STARTED ===")

    system_user = get_system_user()
    today = timezone.localdate()

    logger.info(f"Billing date: {today}")

    rent_count = generate_rent_invoices(
        today,
        system_user,
        properties=properties
    )

    recurring_count = generate_recurring_charge_invoices(
        today,
        system_user,
        properties=properties
    )

    total_created = rent_count + recurring_count

    logger.info(
        f"Monthly billing completed | "
        f"Rent: {rent_count} | "
        f"Recurring: {recurring_count} | "
        f"Total: {total_created}"
    )

    logger.info("=== Monthly billing job COMPLETED ===")

    return {
        "rent_invoices_created": rent_count,
        "recurring_invoices_created": recurring_count,
        "total_created": total_created,
    }


def get_billing_period(today):
    """
    Returns the first and last day of the current month.
    """

    start = today.replace(day=1)

    last_day = calendar.monthrange(today.year, today.month)[1]
    end = today.replace(day=last_day)

    return start, end


def generate_rent_invoices(today, system_user, *, properties=None):

    billing_start, billing_end = get_billing_period(today)

    logger.info(
        f"Generating RENT invoices for period "
        f"{billing_start} to {billing_end}"
    )

    active_tenancies = Tenancy.objects.filter(
        status="ACTIVE",
        start_date__lte=today
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    )

    if properties is not None:
        active_tenancies = active_tenancies.filter(
            unit__property__in=properties
        )

    active_tenancies = active_tenancies.select_related(
        "tenant",
        "unit",
        "unit__property"
    )

    logger.info(
        f"Found {active_tenancies.count()} active tenancies for rent billing"
    )

    invoices_created = 0

    for tenancy in active_tenancies:

        ledger_account = tenancy.ledger_account

        invoice_exists = Invoice.objects.filter(
            ledger_account=ledger_account,
            category=InvoiceCategory.RENT,
            billing_period_start=billing_start,
            billing_period_end=billing_end
        ).exists()

        if invoice_exists:
            logger.info(
                f"Invoice already exists for tenancy {tenancy.id}, "
                f"category RENT"
            )
            continue

        logger.info(
            f"Creating RENT invoice | "
            f"tenancy={tenancy.id} | "
            f"amount={tenancy.rent_amount}"
        )

        create_invoice_service(
            tenancy=tenancy,
            category=InvoiceCategory.RENT,
            amount=tenancy.rent_amount,
            issue_date=today,
            due_date=billing_end,
            billing_period_start=billing_start,
            billing_period_end=billing_end,
            created_by=system_user,
            status=InvoiceStatus.ISSUED,
        )

        invoices_created += 1

    return invoices_created


def generate_recurring_charge_invoices(
    today,
    system_user,
    *,
    properties=None
):

    billing_start, billing_end = get_billing_period(today)

    logger.info("Starting recurring charge billing")

    charges = RecurringCharge.objects.filter(
        is_active=True,
        start_date__lte=today
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    )

    if properties is not None:
        charges = charges.filter(property__in=properties)

    logger.info(f"Found {charges.count()} active recurring charges")

    invoices_created = 0

    for charge in charges:

        logger.info(
            f"Processing charge {charge.id} | "
            f"property={charge.property.id} | "
            f"amount={charge.amount}"
        )

        if charge.day_of_month and today.day < charge.day_of_month:
            logger.info(
                f"Skipping charge {charge.id} - "
                f"waiting for billing day {charge.day_of_month}"
            )
            continue

        unit_types = charge.applies_to_unit_types

        tenancies = Tenancy.objects.filter(
            status="ACTIVE",
            start_date__lte=today,
            unit__property=charge.property,
            unit__unit_type__in=unit_types
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        ).select_related(
            "unit",
            "tenant",
            "unit__property"
        )

        logger.info(
            f"{tenancies.count()} tenancies eligible "
            f"for charge {charge.id}"
        )

        charge_invoices_created = 0

        for tenancy in tenancies:

            ledger_account = tenancy.ledger_account

            invoice_exists = Invoice.objects.filter(
                ledger_account=ledger_account,
                category=charge.category,
                billing_period_start=billing_start,
                billing_period_end=billing_end
            ).exists()

            if invoice_exists:
                logger.info(
                    f"Invoice exists | "
                    f"tenancy={tenancy.id} | "
                    f"charge={charge.id}"
                )
                continue

            logger.info(
                f"Creating charge invoice | "
                f"tenancy={tenancy.id} | "
                f"charge={charge.id} | "
                f"amount={charge.amount}"
            )

            create_invoice_service(
                tenancy=tenancy,
                category=charge.category,
                amount=charge.amount,
                issue_date=today,
                due_date=billing_end,
                billing_period_start=billing_start,
                billing_period_end=billing_end,
                created_by=system_user,
                status=InvoiceStatus.ISSUED,
            )

            charge_invoices_created += 1
            invoices_created += 1

        if charge_invoices_created:
            logger.info(
                f"Charge {charge.id} processed successfully. "
                f"Created {charge_invoices_created} invoices."
            )

            charge.last_generated_date = today
            charge.save(update_fields=["last_generated_date"])

        else:
            logger.warning(
                f"No invoices created for charge {charge.id}"
            )

    return invoices_created
