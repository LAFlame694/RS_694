from django.shortcuts import render
from .services.tenant_service import (
    get_tenants_for_user
)

# Create your views here.
def tenant_list_view(request):
    tenants = get_tenants_for_user(request.user)

    return render(request, "tenants/tenant_list.html", {
        "tenants": tenants
    })