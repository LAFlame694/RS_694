from django import forms
from tenants.models import Tenant
from tenants.choices import TenancyStatus

class AssignTenantForm(forms.Form):
    tenant = forms.ModelChoiceField(
        queryset=Tenant.objects.none(),
        label="Select Tenant",
        widget=forms.Select(attrs={'class': 'form-control', 'placeholder': 'Select Tenant'})
    )

    rent_amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        label="Rent Amount",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter rent amount', 'step': '0.01'})
    )

    start_date = forms.DateField(
        label="Start Date",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )

    def __init__(self, *args, **kwargs):
        available_tenants = kwargs.pop('available_tenants', None)
        super().__init__(*args, **kwargs)

        if available_tenants is not None:
            self.fields['tenant'].queryset = available_tenants