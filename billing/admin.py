from django.contrib import admin
from .models import Invoice, Meter, MeterReading, RecurringCharge, InvoiceSequence
from core.admin_mixins import LandlordFilteredAdmin

# Register your models here.
@admin.register(Invoice)
class InvoiceAdmin(LandlordFilteredAdmin):
    
    landlord_lookup = "tenancy__unit__property__landlord"

    list_display = (
        "invoice_number",
        "tenancy",
        "total_amount",
        "amount_paid",
        "status",
        "issue_date",
        "created_by",
        "is_system_generated",
    )
    list_filter = ("category","created_by__role",)

@admin.register(Meter)
class MeterAdmin(LandlordFilteredAdmin):

    landlord_lookup = "unit__property__landlord"

    list_display = (
        "meter_number",
        "meter_type",
        "unit",
        "is_active",
        "created_at"
    )
    list_filter = ("meter_type", "is_active")
    search_fields = ("meter_number",)

@admin.register(MeterReading)
class MeterReadingAdmin(LandlordFilteredAdmin):

    landlord_lookup = "meter__unit__property__landlord"

    list_display = (
        "meter",
        "reading_date",
        "previous_reading",
        "current_reading",
        "consumption",
        "amount",
        "is_billed",
    )
    list_filter = ("is_billed", "reading_date")
    search_fields = ("meter__meter_number",)

@admin.register(RecurringCharge)
class RecurringChargeAdmin(LandlordFilteredAdmin):

    landlord_lookup = "property__landlord"

    list_display = (
        "category",
        "property",
        "applies_to_unit_types",
        "amount",
        "start_date",
        "is_active",
    )
    list_filter = ("category", "applies_to_unit_types", "is_active",)

# only system_admin should see this model
@admin.register(InvoiceSequence)
class InvoiceSequenceAdmin(admin.ModelAdmin):

    list_display = ("year", "last_number", "created_at")

    def has_module_permission(self, request):
        if not request.user.is_authenticated:
            return False
        
        return request.user.role == "SYSTEM_ADMIN"