from django.contrib import admin
from accounts.models import Role, User

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

        # object creation
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
                    return

        # object editing
        else:
            if "landlord" in form.changed_data:
                form.add_error("landlord", "landlord cannot be changed.")
                return
            
            # prevent tenancy reassignment
            if "tenancy" in form.changed_data:
                form.add_error("tenancy", "Tenancy cannot be changed.")
                return
        
        super().save_model(request, obj, form, change)
    
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
        
        if request.user.role == Role.LANDLORD:
            return self.get_nested_attr(obj, self.landlord_lookup) == request.user
        
        if request.user.role == Role.CARETAKER:
            return self.get_nested_attr(obj, self.landlord_lookup) == request.user.landlord
        
        return False
    
    def has_change_permission(self, request, obj = None):
        # prevents modifying objects outside tenant scope
        if request.user.role == Role.SYSTEM_ADMIN:
            return True
        
        if obj is None:
            return True
        
        if request.user.role == Role.LANDLORD:
            return self.get_nested_attr(obj, self.landlord_lookup) == request.user
        
        if request.user.role == Role.CARETAKER:
            return self.get_nested_attr(obj, self.landlord_lookup) == request.user.landlord
        
        return False
    
    def has_delete_permission(self, request, obj = None):
        # prevent deleting objects belonging to other landlords
        if request.user.role == Role.SYSTEM_ADMIN:
            return True
        
        if obj is None:
            return True
        
        if request.user.role == Role.LANDLORD:
            return self.get_nested_attr(obj, self.landlord_lookup) == request.user
        
        if request.user.role == Role.CARETAKER:
            return self.get_nested_attr(obj, self.landlord_lookup) == request.user.landlord

        return False
    
    def get_nested_attr(self, obj, attr_path):
        """
        Resolves nested attributes eg "property__landlord"
        """
        attrs = attr_path.split("__")
        value = obj

        for attr in attrs:
            value = getattr(value, attr)
        
        return value