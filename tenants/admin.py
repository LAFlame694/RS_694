from django.contrib import admin
from .models import Tenancy, Tenant
from core.admin_mixins import LandlordFilteredAdmin

# Register your models here.
@admin.register(Tenancy)
class TenancyAdmin(LandlordFilteredAdmin):

    landlord_lookup = "unit__property__landlord"
    
    list_display = (
        "tenant",
        "unit",
        "status",
        "start_date",
        "end_date",
        "rent_amount",
    )
    list_filter = ("status",)
    autocomplete_fields = ("tenant", "unit")

@admin.register(Tenant)
class TenantAdmin(LandlordFilteredAdmin):
     
     landlord_lookup = "landlord"

     list_display = (
          "first_name",
          "last_name",
          "phone_number",
          "landlord",
          "is_active",
     )
     search_fields = (
          "first_name",
          "last_name",
          "phone_number",
          "id_number",
     )
     list_filter = ("is_active",)