from django.urls import path

from finance.views.payment_views import (
    search_tenant_for_payment_view,
    record_payment_view,
    payment_search_view,
    tenant_payment_history_view,
    payment_detail_view,
    payment_allocations_view,
)

app_name = "finance"

urlpatterns = [
    path(
        "payments/search/",
        payment_search_view,
        name="payment_search"
    ),

    path(
        "payments/history/<int:tenant_id>/",
        tenant_payment_history_view,
        name="tenant_payment_history"
    ),

    path(
        "payments/<int:payment_id>/",
        payment_detail_view,
        name="payment_detail"
    ),

    path(
        "payments/<int:payment_id>/allocations/",
        payment_allocations_view,
        name="payment_allocations"
    ),

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