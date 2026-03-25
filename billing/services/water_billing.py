import logging
from django.db import transaction
from django.utils import timezone

from finance.models import LedgerEntry
from finance.choices import LedgerEntryCategory, LedgerEntryType
from billing.models import Invoice, MeterReading
from tenants.models import Tenancy
from tenants.choices import TenancyStatus
from billing.choices import MeterReadingStatus, InvoiceStatus

from accounts.utils import get_system_user

logger = logging.getLogger("billing")

def generate_invoice_from_meter_reading(reading):
    """
    Generates invoice + ledger entry from a meter reading.
    """

    if not reading.can_be_billed():
        logger.warning(f"Reading {reading.id} already billed or invalid")
        return None
    
    # retrieve the tenancy associated with the meter reading
    unit = reading.meter.unit

    tenancy = Tenancy.objects.filter(
        unit=unit,
        status=TenancyStatus.ACTIVE
    ).first()

    if not tenancy:
        logger.warning(f"No active tenancy for meter reading {reading.id}")
        return None
    
    system_user = get_system_user()

    try:
        with transaction.atomic():
            # create invoice
            invoice = Invoice.objects.create(
                tenancy=tenancy,
                ledger_account=tenancy.ledger_account,
                category=LedgerEntryCategory.WATER,
                issue_date=timezone.now().date(),
                due_date=timezone.now().date(),
                total_amount=reading.amount,
                status=InvoiceStatus.ISSUED,
                created_by=system_user
            )

            # create ledger entry
            LedgerEntry.objects.create(
                ledger_account=tenancy.ledger_account,
                category=LedgerEntryCategory.WATER,
                amount=reading.amount,
                entry_type=LedgerEntryType.CHARGE,
                entry_date=reading.reading_date,
                invoice=invoice,
                created_by=system_user
            )

            # update reading
            MeterReading.objects.filter(pk=reading.pk).update(
                status=MeterReadingStatus.BILLED,
                invoice=invoice,
                billed_by=system_user,
                billed_at=timezone.now()
            )

            logger.info(
                f"Water invoice created | reading={reading.id} | invoice={invoice.invoice_number}"
            )

            return invoice
    
    except Exception as e:
        logger.error(
            f"Failed to generate invoice for reading {reading.id} | error={str(e)}",
            exc_info=True
        )
        return None
