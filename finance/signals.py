from django.db.models.signals import post_save
from django.dispatch import receiver

from tenants.models import Tenancy
from finance.models import LedgerAccount

@receiver(post_save, sender=Tenancy)
def create_ledger_account(sender, instance, created, **kwargs):
    if created:
        LedgerAccount.objects.get_or_create(
            tenancy=instance
        )