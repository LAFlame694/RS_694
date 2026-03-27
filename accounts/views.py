from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .choices import Role

# Create your views here.
def login_view(request):
    if request.user.is_authenticated:
        return redirect_user_dashboard(request, request.user)
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect_user_dashboard(request, user)
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'accounts/login.html')

def redirect_user_dashboard(request, user):
    if user.role == Role.LANDLORD:
        return redirect('landlord_dashboard')
    
    elif user.role == Role.CARETAKER:
        return redirect('caretaker_dashboard')
    
    elif user.role == Role.SYSTEM_ADMIN:
        return redirect('admin:index') # django admin
    
    return redirect('login')


from .decorators import landlord_required, caretaker_required
from django.http import HttpResponse

@landlord_required
def landlord_dashboard(request):
    return render(request, 'dashboard/landlord/dashboard.html')

@caretaker_required
def caretaker_dashboard(request):
    return render(request, 'dashboard/caretaker/dashboard.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')