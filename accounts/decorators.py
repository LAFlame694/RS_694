from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .choices import Role

def landlord_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role == Role.LANDLORD:
            return view_func(request, *args, **kwargs)
        return redirect('login')  # Redirect to login page
    return wrapper

def caretaker_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role == Role.CARETAKER:
            return view_func(request, *args, **kwargs)
        return redirect('login')  # Redirect to login page
    return wrapper