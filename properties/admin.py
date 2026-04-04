from django.contrib import admin
from .models import Property, Unit
from core.admin_mixins import LandlordFilteredAdmin

# Register your models here.
@admin.register(Property)
class PropertyAdmin(LandlordFilteredAdmin):

    landlord_lookup = "landlord"

    list_display = (
        "name",
        "landlord",
        "country",
        "is_active",
        "created_at"
    )
    search_fields = ("name", "city")

@admin.register(Unit)
class UnitAdmin(LandlordFilteredAdmin):

    landlord_lookup = "property__landlord"

    list_display = ("unit_number", "property", "unit_type", "status", "is_active",)
    search_fields = ("unit_number",)