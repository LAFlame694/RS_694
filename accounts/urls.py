from django.urls import path
from . import views
from .views import login_view, landlord_dashboard, caretaker_dashboard
urlpatterns = [
    path('login/', login_view, name='login'),
    path('landlord/dashboard/', landlord_dashboard, name='landlord_dashboard'),
    path('caretaker/dashboard/', caretaker_dashboard, name='caretaker_dashboard'),
    path('logout/', views.logout_view, name='logout'),
]