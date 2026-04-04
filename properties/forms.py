from django import forms
from tenants.models import Tenant
from tenants.choices import TenancyStatus
from django.utils import timezone
from .models import Unit, Property

class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            "name", 
            "description",
            "address_line_1",
            "address_line_2",
            "country",
            "county",
            "postal_code",
            "is_active",
        ]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter property name"
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Optional description"
            }),
            "address_line_1": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Address line 1"
            }),
            "address_line_2": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Address line 2 (optional)"
            }),
            "country": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Country"
            }),
            "county": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "County"
            }),
            "postal_code": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Postal code"
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
        }
    
    # custom validation
    def clean_name(self):
        name = self.cleaned_data.get("name")

        if not name:
            raise forms.ValidationError("Property name is required.")
        
        return name.strip()

class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ['unit_number', 'unit_type', 'floor']

        widgets = {
            'unit_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter unit number'}),
            'unit_type': forms.Select(attrs={'class': 'form-control'}),
            'floor': forms.TextInput(attrs={'class': 'form-control' , 'placeholder': 'Enter floor number'}),
        }

    def __init__(self, *args, **kwargs):
        self.property = kwargs.pop('property', None)
        super().__init__(*args, **kwargs)

    def clean_unit_number(self):
        unit_number = self.cleaned_data['unit_number'].upper()

        if not self.property:
            return unit_number  # skip validation safely

        if Unit.objects.filter(
            property=self.property,
            unit_number=unit_number
        ).exists():
            raise forms.ValidationError(
                "This unit number already exists for this property."
            )

        return unit_number

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
    
    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')

        if not start_date:
            return timezone.now().date()
        
        return start_date
    
    def clean_rent_amount(self):
        rent = self.cleaned_data.get('rent_amount')

        if rent is None or rent <= 0:
            raise forms.ValidationError("Rent amount must be greater than 0.")
        
        return rent

class EditUnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ['unit_number', 'unit_type', 'floor', 'is_active']

        widgets = {
            'unit_number': forms.TextInput(attrs={'class': 'form-control'}),
            'unit_type': forms.Select(attrs={'class': 'form-control'}),
            'floor': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_unit_number(self):
        unit_number = self.cleaned_data.get('unit_number')
        property = self.instance.property

        # prevent duplicate within same property
        if Unit.objects.filter(
            property=property,
            unit_number=unit_number
        ).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("This unit number already exists in this property.")
        
        return unit_number
