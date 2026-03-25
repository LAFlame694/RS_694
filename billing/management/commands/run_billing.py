import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from finance.services.billing_service import generate_monthly_billing

logger = logging.getLogger("billing")

class Command(BaseCommand):
    help = "Runs monthly billing (rent + recurring charges)."

    def handle(self, *args, **options):
        logger.info("=== Monthly billing job started ===")
        
        try:
            with transaction.atomic():
                generate_monthly_billing()

            logger.info("=== Monthly billing job COMPLETED SUCCESSFULLY ===")
        
        except Exception as e:
            logger.error(
                f"=== Monthly billing job FAILED === | Error: {str(e)}",
            exc_info=True
            )
            raise