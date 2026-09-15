import logging
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from finance.choices import LedgerEntryType, LedgerEntryCategory, SourceChoices
from finance.models import LedgerEntry, Payment
from finance.services.credit_service import apply_available_credit_to_invoices

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
    
    try:
        # validate amount
        if amount is None:
            raise ValidationError(
                "Payment amount is required."
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

        # record payment and automatically apply
        # available NORMAL credit to invoices.
        with transaction.atomic():

            payment = Payment.objects.create(
                ledger_account=ledger_account,
                amount=amount,
                payment_date=payment_date,
                method=method,
                created_by=created_by
            )

            # payment enter the NORMAL credit pool
            LedgerEntry.objects.create(
                ledger_account=ledger_account,
                payment=payment,
                category=LedgerEntryCategory.PAYMENT,
                entry_type=LedgerEntryType.CREDIT,
                source=SourceChoices.NORMAL,
                amount=payment.amount,
                entry_date=payment.payment_date,
                description=(
                    f"Payment received - "
                    f"{payment.reference_code}"
                ),
                created_by=created_by
            )

            # automatically apply NORMAL credit 
            # to the oldest outstanding invoices.
            applied_amount = apply_available_credit_to_invoices(
                ledger_account=ledger_account,
                created_by=created_by,
                entry_date=payment.payment_date
            )

            logger.info(
                f"Payment recorded successfully | " 
                f"payment={payment.id} | " 
                f"tenant={tenant.id} | " 
                f"amount={amount} | " 
                f"credit_applied={applied_amount}"
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
            "Unable to record payment at the moment. "
            "Please try again."
        )