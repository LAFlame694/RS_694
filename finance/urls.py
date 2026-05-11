from django.urls import path

from finance.views.payment_views import (
    search_tenant_for_payment_view,
    record_payment_view,
)

app_name = "finance"

urlpatterns = [
    path(
        "payments/record/",
        search_tenant_for_payment_view,
        name="search_tenant_for_payment"
    ),

    path(
        "payments/record/<int:tenant_id>/",
        record_payment_view,
        name="record_payment",
    ),
]