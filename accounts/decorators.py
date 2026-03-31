from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .choices import Role
from django.http import HttpResponseForbidden

def landlord_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role == Role.LANDLORD:
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("Not allowed")  # Return 403 Forbidden response
    return wrapper

def caretaker_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role == Role.CARETAKER:
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("Not allowed")  # Return 403 Forbidden response
    return wrapper