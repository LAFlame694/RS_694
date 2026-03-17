from django.contrib import admin
from .models import LedgerAccount, LedgerEntry, Payment
from core.admin_mixins import LandlordFilteredAdmin
from accounts.models import Role

# Register your models here.
@admin.register(LedgerAccount)
class LedgerAccountAdmin(LandlordFilteredAdmin):

    landlord_lookup = "tenancy__unit__property__landlord"

    list_display = (
        "account_number", 
        "tenancy", 
        "is_active", 
        "created_at"
    )
    readonly_fields = ("account_number", "created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))

        if obj is not None:
            readonly.append("tenancy")
        
        return readonly

    def get_exclude(self, request, obj=None):
        exclude = super().get_exclude(request, obj) or []

        if obj is None:
            # hide tenancy only for landlord and caretaker
            if request.user.role in [Role.LANDLORD, Role.CARETAKER]:
                exclude = list(exclude) + ["tenancy"]
        
        return exclude
    
    def has_add_permission(self, request):
        return request.user.role == Role.SYSTEM_ADMIN

@admin.register(LedgerEntry)
class LedgerEntryAdmin(LandlordFilteredAdmin):

    landlord_lookup = "ledger_account__tenancy__unit__property__landlord"

    list_display = (
        "entry_type",
        "category",
        "amount",
        "entry_date",
        "reference_code",
    )
    list_filter = ("entry_type", "category")

@admin.register(Payment)
class PaymentAdmin(LandlordFilteredAdmin):

    landlord_lookup = "ledger_account__tenancy__unit__property__landlord"

    list_display = (
        "reference_code",
        "ledger_account",
        "amount",
        "method",
        "payment_date",
    )
    list_filter = ("method", "payment_date")
    search_fields = ("reference_code",)
