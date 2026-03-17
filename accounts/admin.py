from django.contrib import admin
from .models import User, Role
from django.contrib.auth.admin import UserAdmin

# Register your models here.
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "role",
        "landlord",
        "is_active"
    )

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Role Information", {"fields": ("role", "landlord")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "email", "phone_number")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username",
                "password1",
                "password2",
                "role",
                "landlord",
                "phone_number",
                "is_active"
            ),
        }),
    )

    search_fields = ("username", "phone_number")
    list_filter = ("role", "is_active")

    def has_module_permission(self, request):
        if not request.user.is_authenticated:
            return False
        return request.user.role == Role.SYSTEM_ADMIN
    
    def has_view_permission(self, request, obj = None):
        if not request.user.is_authenticated:
            return False
        return request.user.role == Role.SYSTEM_ADMIN