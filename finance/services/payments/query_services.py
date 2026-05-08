import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum

from billing.models import Invoice
from billing.choices import InvoiceStatus
from finance.models import DepositAllocation
from finance.services.payments.calculation_services import calculate_outstanding_balance
from tenants.models import Tenancy
from tenants.choices import TenancyStatus
from finance.services.credit_service import get_available_credit

logger = logging.getLogger("query_service")

def get_unpaid_invoices(*, tenant, limit=5):
    """
    Returns oldest unpaid invoices for a tenant.
    """
    try:
        tenancy = Tenancy.objects.select_related(
            "ledger_account"
        ).get(
            tenant=tenant,
            status=TenancyStatus.ACTIVE
        )

        invoices = Invoice.objects.filter(
            ledger_account=tenancy.ledger_account,
            status__in=[
                InvoiceStatus.ISSUED,
                InvoiceStatus.PARTIAL,
            ]
        ).order_by("issue_date", "id")[:limit]

        return invoices
    except Tenancy.DoesNotExist:
        logger.warning(
            f"No active tenancy found | tenant={tenant.id}"
        )
        raise ValidationError(
            "Tenant does not have an active tenancy."
        )
    
    except Exception as e:
        logger.error(
            f"Failed to fetch unpaid invoices | tenant={tenant.id} | error={str(e)}",
            exc_info=True
        )
        raise

def get_tenant_financial_summary(*, tenant):
    """
    Returns financial summery data for record payment UI.
    """

    try:
        tenancy = Tenancy.objects.select_related(
            "unit__property",
            "ledger_account"
        ).get(
            tenant=tenant,
            status=TenancyStatus.ACTIVE
        )

        ledger_account = tenancy.ledger_account

        outstanding_balance = calculate_outstanding_balance(
            ledger_account=ledger_account
        )

        available_credit = get_available_credit(
            ledger_account=ledger_account
        )

        deposit_held = DepositAllocation.objects.filter(
            ledger_account=ledger_account
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        unpaid_invoice_count = Invoice.objects.filter(
            ledger_account=ledger_account,
            status__in=[
                InvoiceStatus.ISSUED,
                InvoiceStatus.PARTIAL,
            ]
        ).count()

        return {
            "tenant": tenant,
            "tenancy": tenancy,
            "property": tenancy.unit.property,
            "unit": tenancy.unit,
            "ledger_account": ledger_account,
            "outstanding_balance": outstanding_balance,
            "available_credit": available_credit,
            "deposit_held": deposit_held,
            "unpaid_invoice_count": unpaid_invoice_count,
        }
    
    except Tenancy.DoesNotExist:
        logger.warning(
            f"No active tenancy found | tenant={tenant.id}"
        )
        raise ValidationError(
            "Tenant does not have an active tenancy"
        )
    
    except Exception as e:
        logger.error(
            f"Failed to fetch tenant financial summery | tenant={tenant.id} | error={str(e)}",
        )
        raise