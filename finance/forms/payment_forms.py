from django import forms

from finance.models import Payment
from finance.choices import PaymentMethod

class RecordPaymentForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=20,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter payment amount",
            }
        )
    )

    payment_date = forms.DateField(
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        )
    )

    method = forms.ChoiceField(
        choices=PaymentMethod.choices,
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        )
    )

    notes = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "placeholder": "Enter payment notes",
                "rows": 3
            }
        )
    )