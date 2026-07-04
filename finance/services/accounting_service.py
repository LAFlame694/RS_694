import logging
from django.db import transaction
from decimal import Decimal

from billing.choices import InvoiceStatus
from billing.models import Invoice
from billing.services.payment_service import apply_payment_to_invoices
from finance.services.credit_service import apply_credit_to_invoices
from finance.models import Payment, PaymentAllocation, CreditAllocation
from finance.choices import PaymentStatus

logger = logging.getLogger("accounting")

def settle_account(ledger_account):
    with transaction.atomic():

        PaymentAllocation.objects.filter(
            payment__ledger_account=ledger_account
        ).delete()

        CreditAllocation.objects.filter(
            payment__ledger_account=ledger_account
        ).delete()

        # reset invoice balances/status
        invoices = Invoice.objects.filter(
            ledger_account=ledger_account
        )

        for invoice in invoices:
            invoice.amount_paid = Decimal("0.00")
            invoice.status = InvoiceStatus.ISSUED
            invoice.save(update_fields=["amount_paid", "status"])

        # STEP 2: APPLY ALL ACTIVE PAYMENTS
        """payments = Payment.objects.filter(
            ledger_account=ledger_account,
            status=PaymentStatus.COMPLETED
        ).order_by("created_at", "id")

        for payment in payments:
            apply_payment_to_invoices(payment)"""

        # STEP 3: APPLY CREDIT LAST
        apply_credit_to_invoices(ledger_account)