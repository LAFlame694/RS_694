import logging

from finance.services.billing_service import (
    generate_monthly_billing as run_monthly_billing,
)

logger = logging.getLogger("billing")

def generate_manual_monthly_billing(*, properties, triggered_by):

    if properties is None:
        raise ValueError("Properties must be provided for manual billing.")

    logger.info(
        "Manual monthly billing initiated | "
        f"Triggered by: {triggered_by} | "
        f"Role: {triggered_by.role}"
    )

    result = run_monthly_billing(properties=properties)

    logger.info(
        "Manual monthly billing completed | "
        f"Triggered by: {triggered_by} | "
        f"Role: {triggered_by.role}"
    )

    return result