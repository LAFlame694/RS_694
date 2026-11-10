from django.urls import path
from billing.views.invoice_views import invoice_list_view

app_name = "billing"

# Create your urls here.
urlpatterns = [
    path("invoices/", invoice_list_view, name="invoice_list"),
]