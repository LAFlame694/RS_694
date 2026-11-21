from django.urls import path

from billing.services.monthly_billing import generate_manual_monthly_billing
from billing.views.invoice_views import (
    invoice_list_view,
    create_invoice_view,
    generate_monthly_billing_view,
    invoice_detail_view
)

app_name = "billing"

# Create your urls here.
urlpatterns = [
    path("invoices/", invoice_list_view, name="invoice_list"),
    path("invoices/create/", create_invoice_view, name="invoice_create"),
    path("invoices/generate-monthly/", generate_monthly_billing_view, name="generate_monthly_billing"),

    path("invoices/<int:invoice_id>/", invoice_detail_view, name="invoice_detail"),
]