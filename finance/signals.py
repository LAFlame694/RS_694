from django.db.models.signals import post_save
from django.dispatch import receiver

from tenants.models import Tenancy
from finance.models import LedgerAccount

from finance.models import Payment
from billing.services.payment_service import apply_payment_to_invoices

@receiver(post_save, sender=Tenancy)
def create_ledger_account(sender, instance, created, **kwargs):
    if created:
        LedgerAccount.objects.get_or_create(
            tenancy=instance
        )

@receiver(post_save, sender=Payment)
def handle_payment_created(sender, instance, created, **kwargs):
    if created:
        apply_payment_to_invoices(instance)