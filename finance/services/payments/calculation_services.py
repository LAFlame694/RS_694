from decimal import Decimal
import logging
from django.db.models import F

from billing.models import Invoice
from billing.choices import InvoiceStatus

logger = logging.getLogger("calculation_service")

def calculate_outstanding_balance(*, ledger_account):
    try:
        invoices = Invoice.objects.filter(
            ledger_account=ledger_account,
            status=InvoiceStatus.ISSUED,
            total_amount__gt=F("amount_paid"),
        )

        total_outstanding = Decimal("0.00")

        for invoice in invoices:
            balance = invoice.total_amount - invoice.amount_paid

            if balance > Decimal("0.00"):
                total_outstanding += balance
            
        return total_outstanding
    
    except Exception as e:
        logger.error(
            f"Failed to calculate outstanding balance | ledger_account={ledger_account.id} | error={str(e)}",
            exc_info=True
        )
        raise