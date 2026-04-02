from django.urls import path
from .views import property_list
from . import views

urlpatterns = [
    path('', property_list, name='property_list'),
    path('properties/<int:property_id>/units/', views.property_units, name='property_units'),
    path('<int:unit_id>/assign-tenant/', views.assign_tenant, name='assign_tenant'),
    path('<int:unit_id>/vacate/', views.vacate_unit_view, name='vacate_unit'),
    path('units/<int:unit_id>/delete/', views.delete_unit_view, name='delete_unit')
]