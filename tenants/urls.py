from django.urls import path
from . import views

app_name = "tenants"

urlpatterns = [
    path('', views.tenant_list_view, name='tenant_list'),
    path('add/', views.add_tenant_view, name='add_tenant'),
    path('assign/<int:tenant_id>/', views.assign_tenant_view, name="assign_tenant"),
    path('tenants/<int:tenant_id>/edit/', views.edit_tenant, name='edit_tenant'),
]