from django import forms

from tenants.models import Tenant
from accounts.models import User
from accounts.choices import Role

# ceate your forms here.
class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = [
            "first_name",
            "last_name",
            "phone_number",
            "email",
            "id_number",
            "landlord" # only used by system admin
        ]
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # hide landlord field unless system admin
        if user and user.role != Role.SYSTEM_ADMIN:
            self.fields.pop("landlord")
        else:
            self.fields["landlord"].queryset = User.objects.filter(role=Role.LANDLORD)