from django.urls import path
from . import views

urlpatterns = [
    path('', views.tenant_list_view, name='tenant_list'),
    path('add/', views.add_tenant_view, name='add_tenant'),
    path('assign/<int:tenant_id>/', views.assign_tenant_view, name="assign_tenant"),
]