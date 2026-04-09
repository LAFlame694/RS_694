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
        ]

        widgets = {
            "first_name": forms.TextInput(attrs={
                "class": "form-control",
            }),
            "last_name": forms.TextInput(attrs={
                "class": "form-control",
            }),
            "phone_number": forms.TextInput(attrs={
                "class": "form-control",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
            }),
            "id_number": forms.TextInput(attrs={
                "class": "form-control",
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)