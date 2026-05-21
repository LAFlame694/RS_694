import logging
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from finance.choices import LedgerEntryType, LedgerEntryCategory, SourceChoices
from finance.models import LedgerEntry, Payment
from finance.services.accounting_service import settle_account

from tenants.models import Tenancy
from tenants.choices import TenancyStatus

logger = logging.getLogger("payment_service")

def record_payment_service(
        *,
        tenant,
        amount,
        payment_date,
        method,
        created_by,
):
    
    """
    Records a payment and automatically 
    allocates it to oldest invoices
    """

    try:
        # validate amount
        if amount is None:
            raise ValidationError(
                "Payment amount is required"
            )
        
        try:
            amount = Decimal(amount)
        except (InvalidOperation, TypeError):
            raise ValidationError(
                "Invalid payment amount."
            )
        
        if amount <= 0:
            raise ValidationError(
                "Payment amount must be greater than zero."
            )
        
        # get active tenancy
        tenancy = Tenancy.objects.select_related(
            "ledger_account"
        ).get(
            tenant=tenant,
            status=TenancyStatus.ACTIVE
        )

        ledger_account = tenancy.ledger_account

        # create payment + allocate
        with transaction.atomic():

            payment = Payment.objects.create(
                ledger_account=ledger_account,
                amount=amount,
                payment_date=payment_date,
                method=method,
                created_by=created_by,
            )

            LedgerEntry.objects.create(
                ledger_account=ledger_account,
                payment=payment,
                category=LedgerEntryCategory.PAYMENT,
                entry_type=LedgerEntryType.CREDIT,
                source=SourceChoices.NORMAL,
                amount=payment.amount,
                entry_date=payment.payment_date,
                description=f"Payment received - {payment.reference_code}",
                created_by=created_by
            )

            # allocate payment to invoices
            settle_account(ledger_account)

            logger.info(
                f"Payment recorded successfully | "
                f"payment={payment.id} | "
                f"tenant={tenant.id} | "
                f"amount={amount}"
            )

            return payment
        
    except Tenancy.DoesNotExist:
        logger.warning(
            f"Payment recording failed | "
            f"tenant={tenant.id} has no active tenancy"
        )

        raise ValidationError(
            "Tenant does not have an active tenancy."
        )
    
    except ValidationError:
        raise

    except Exception as e:

        logger.error(
            f"Payment recording failed | "
            f"tenant={tenant.id} | "
            f"error={str(e)}",
            exc_info=True
        )

        raise ValidationError(
            "Unable to record payment at the moment. Please try again."
        )