from django.contrib import admin
from accounts.models import Role, User
import logging

logger = logging.getLogger("admin")

"""
custom base class for Django Admin that 
restricts what data a user can see depending on their role
"""
class LandlordFilteredAdmin(admin.ModelAdmin):
    """base admin class that isolates landlord data"""

    landlord_lookup = None

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.role == Role.SYSTEM_ADMIN:
            return qs

        if not self.landlord_lookup:
            return qs.none()
        
        if request.user.role == Role.LANDLORD:
            return qs.filter(**{self.landlord_lookup: request.user})
        
        if request.user.role == Role.CARETAKER:
            return qs.filter(**{self.landlord_lookup: request.user.landlord})
        
        return qs.none()
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        landlord = None

        if request.user.role == Role.LANDLORD:
            landlord = request.user
        
        elif request.user.role == Role.CARETAKER:
            landlord = request.user.landlord
        
        # property filter
        if db_field.name == "property" and landlord:
            from properties.models import Property
            kwargs["queryset"] = Property.objects.filter(landlord=landlord)
        
        # ledger account filter
        if db_field.name == "ledger_account" and landlord:
            from finance.models import LedgerAccount
            kwargs["queryset"] = LedgerAccount.objects.filter(tenancy__unit__property__landlord=landlord)
        
        # tenant filter
        if db_field.name == "tenant" and landlord:
            from tenants.models import Tenant
            kwargs["queryset"] = Tenant.objects.filter(landlord=landlord)
        
        # unit filter
        if db_field.name == "unit" and landlord:
            from properties.models import Unit
            kwargs["queryset"] = Unit.objects.filter(property__landlord=landlord)
        
        if db_field.name == "tenancy" and landlord:
            from tenants.models import Tenancy
            kwargs["queryset"] = Tenancy.objects.filter(unit__property__landlord=landlord)

        # created_by filter
        if db_field.name == "created_by":

            if request.user.role == Role.LANDLORD:
                kwargs["queryset"] = User.objects.filter(
                    landlord=request.user
                ) | User.objects.filter(id=request.user.id)
            
            elif request.user.role == Role.CARETAKER:
                kwargs["queryset"] = User.objects.filter(
                    landlord=request.user.landlord
                ) | User.objects.filter(id=request.user.landlord.id)
        
        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs
        )
    
    def save_model(self, request, obj, form, change):

        fields = [f.name for f in obj._meta.fields]


        # ===== CREATE OBJECT =====
        if not change:
            if "created_by" in fields:
                obj.created_by = request.user
            
            if "landlord" in fields:
                
                # landlord creating object
                if request.user.role == Role.LANDLORD:
                    obj.landlord = request.user
                
                # caretaker creating object
                elif request.user.role == Role.CARETAKER:
                    obj.landlord = request.user.landlord
                
                # system admin must choose landlord manually
                elif request.user.role == Role.SYSTEM_ADMIN and not obj.landlord:
                    form.add_error("landlord", "Landlord must be selected.")
                    logger.warning(
                        f"ADMIN CREATE FAILED | user={request.user.username} | "
                        f"model={obj.__class__.__name__} | reason=missing landlord"
                    )
                    return

        # ===== OBJECT EDITING =====
        else:
            if "landlord" in form.changed_data:
                form.add_error("landlord", "landlord cannot be changed.")
                logger.warning(
                    f"ADMIN UPDATE BLOCKED | user={request.user.username} | "
                    f"model={obj.__class__.__name__} | id={obj.id} | field=landlord"
                )
                return
            
            # prevent tenancy reassignment
            if "tenancy" in form.changed_data:
                form.add_error("tenancy", "Tenancy cannot be changed.")
                logger.warning(
                    f"ADMIN UPDATE BLOCKED | user={request.user.username} | "
                    f"model={obj.__class__.__name__} | id={obj.id} | field=tenancy"
                )
                return

        # save first
        super().save_model(request, obj, form, change)

        # ===== LOG AFTER SAVE =====
        if change:
            logger.info(
                f"ADMIN UPDATE | user={request.user.username} | "
                f"model={obj.__class__.__name__} | id={obj.id}"
            )

            # field level changes
            for field in form.changed_data:
                old_value = form.initial.get(field)
                new_value = getattr(obj, field)

                logger.info(
                    f"FIELD CHANGE | user={request.user.username} | "
                    f"model={obj.__class__.__name__} | id={obj.id} | "
                    f"field={field} | from={old_value} | to={new_value}"
                )
        
        else:
            logger.info(
                f"ADMIN CREATE | user={request.user.username} | "
                f"model={obj.__class__.__name__} | id={obj.id}"
            )
    
    def delete_model(self, request, obj):
        logger.warning(
            f"ADMIN DELETE | user={request.user.username} | "
            f"model={obj.__class__.__name__} | id={obj.id}"
        )
        super().delete_model(request, obj)
    
    def delete_queryset(self, request, queryset):
        for obj in queryset:
            logger.warning(
                f"ADMIN BULK DELETE | user={request.user.username} | "
                f"model={obj.__class__.__name__} | id={obj.id}"
            )
        super().delete_queryset(request, queryset)
    
    def get_exclude(self, request, obj = None):
        exclude = list(super().get_exclude(request, obj) or [])

        # hide only for landlords and caretakers
        if request.user.role in [Role.LANDLORD, Role.CARETAKER]:

            if obj is None: # only on creation
                if hasattr(self.model, "created_by"):
                    exclude.append("created_by")

                if hasattr(self.model, "landlord"):
                    exclude.append("landlord")
        
        return exclude
    
    def get_readonly_fields(self, request, obj = None):
        readonly = list(super().get_readonly_fields(request, obj) or [])

        if obj is not None:
            if hasattr(self.model, "landlord"):
                readonly.append("landlord")
            
            if hasattr(self.model, "created_by"):
                readonly.append("created_by")

        return readonly
    
    def has_view_permission(self, request, obj = None):
        # prevents opening objects outside tenant scope
        if request.user.role == Role.SYSTEM_ADMIN:
            return True
        
        if obj is None:
            return True

        allowed = False
        
        if request.user.role == Role.LANDLORD:
            allowed = self.get_nested_attr(obj, self.landlord_lookup) == request.user
        
        elif request.user.role == Role.CARETAKER:
            allowed = self.get_nested_attr(obj, self.landlord_lookup) == request.user.landlord
        
        if not allowed:
            logger.warning(
                f"VIEW DENIED | user={request.user.username} | "
                f"model={obj.__class__.__name__} | id={obj.id}"
            )
        
        return allowed
    
    def has_change_permission(self, request, obj = None):
        # prevents modifying objects outside tenant scope
        if request.user.role == Role.SYSTEM_ADMIN:
            return True
        
        if obj is None:
            return True
        
        allowed = False
        
        if request.user.role == Role.LANDLORD:
            allowed = self.get_nested_attr(obj, self.landlord_lookup) == request.user
        
        elif request.user.role == Role.CARETAKER:
            allowed = self.get_nested_attr(obj, self.landlord_lookup) == request.user.landlord
        
        if not allowed:
            logger.warning(
                f"CHANGE DENIED | user={request.user.username} | "
                f"model={obj.__class__.__name__} | id={obj.id}"
            )
        return allowed
    
    def has_delete_permission(self, request, obj = None):
        # prevent deleting objects belonging to other landlords
        if request.user.role == Role.SYSTEM_ADMIN:
            return True
        
        if obj is None:
            return True
        
        allowed = False
        
        if request.user.role == Role.LANDLORD:
            allowed = self.get_nested_attr(obj, self.landlord_lookup) == request.user
        
        if request.user.role == Role.CARETAKER:
            allowed = self.get_nested_attr(obj, self.landlord_lookup) == request.user.landlord
        
        if not allowed:
            logger.warning(
                f"DELETE DENIED | user={request.user.username} | "
                f"model={obj.__class__.__name__} | id={obj.id}"
            )

        return allowed
    
    def get_nested_attr(self, obj, attr_path):
        """
        Resolves nested attributes eg "property__landlord"
        """
        attrs = attr_path.split("__")
        value = obj

        for attr in attrs:
            value = getattr(value, attr)
        
        return value