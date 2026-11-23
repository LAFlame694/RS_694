from django.urls import path

from billing.services.monthly_billing import generate_manual_monthly_billing
from billing.views.invoice_views import (
    invoice_list_view,
    create_invoice_view,
    generate_monthly_billing_view,
    invoice_detail_view,
    delete_draft_invoice_view,
    issue_invoice_view,
    cancel_invoice_view,
    update_draft_invoice_view
)

app_name = "billing"

# Create your urls here.
urlpatterns = [
    path("invoices/", invoice_list_view, name="invoice_list"),
    path("invoices/create/", create_invoice_view, name="invoice_create"),
    path("invoices/generate-monthly/", generate_monthly_billing_view, name="generate_monthly_billing"),

    path("invoices/<int:invoice_id>/", invoice_detail_view, name="invoice_detail"),
    path("invoices/<int:invoice_id>/delete/", delete_draft_invoice_view, name="delete_invoice"),
    path("invoices/<int:invoice_id>/issue/", issue_invoice_view, name="issue_invoice"),
    path("invoices/<int:invoice_id>/cancel/", cancel_invoice_view, name="cancel_invoice"),
    path("invoices/<int:invoice_id>/edit/", update_draft_invoice_view, name="edit_invoice")
]