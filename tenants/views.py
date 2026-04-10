from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError

from .forms import TenantForm
from .models import Tenant
from properties.models import Unit
from properties.choices import UnitStatus
from properties.services.unit_service import assign_tenant_to_unit
from .services.tenant_service import (
    get_tenants_for_user,
    create_tenant,
    update_tenant
)

# Create your views here.
@login_required
def edit_tenant(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)

    if request.method == 'POST':
        form = TenantForm(request.POST, instance=tenant)

        if form.is_valid():
            try:
                update_tenant(tenant, form.cleaned_data)

                messages.success(request, "Tenant updated successfully.")
                return redirect('tenants:tenant_list')
            
            except ValidationError as e:
                form.add_error(None, e.message)
            
            except IntegrityError:
                # handle db constraint
                form.add_error("phone_number", "This phone number is already used by another tenant.")
        else:
            print(form.errors)
    else:
        form = TenantForm(instance=tenant)
    
    return render(request, "tenants/edit_tenant.html", {
        'form': form,
        'tenant': tenant
    })

@login_required
def assign_tenant_view(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)

    # get available units (same landlord + vacant units only)
    available_units = Unit.objects.filter(
        property__landlord=tenant.landlord,
        status=UnitStatus.VACANT
    ).select_related("property")

    if request.method == "POST":
        unit_id = request.POST.get("unit")
        rent_amount = request.POST.get("rent_amount")
        start_date = request.POST.get("start_date")

        try:
            unit = Unit.objects.get(id=unit_id)

            assign_tenant_to_unit(
                unit=unit,
                tenant=tenant,
                rent_amount=rent_amount,
                start_date=start_date,
                created_by=request.user
            )

            messages.success(request, "Tenant assigned successfully.")
            return redirect("tenants:tenant_list")
        except ValidationError as e:
            messages.error(request, e.message)
        
        except Unit.DoesNotExist:
            messages.error(request, "Invalid unit selected.")
    
    return render(request, "tenants/assign_tenant_to_unit.html", {
        "tenant": tenant,
        "available_units": available_units
    })

def add_tenant_view(request):
    if request.method == "POST":
        form = TenantForm(request.POST, user=request.user)
        
        if form.is_valid():
            try:
                create_tenant(
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    phone_number=form.cleaned_data["phone_number"],
                    email=form.cleaned_data.get("email"),
                    id_number=form.cleaned_data.get("id_number"),
                    landlord=form.cleaned_data.get("landlord"),
                    created_by=request.user
                )
                
                messages.success(request, "Tenant created successfully.")
                return redirect("tenants:tenant_list")
            
            except ValidationError as e:
                form.add_error(None, e.message)
    else:
        form = TenantForm(user=request.user)
    
    return render(request, "tenants/add_tenant.html", {
        "form": form
    })

def tenant_list_view(request):
    search_query = request.GET.get("q")
    status = request.GET.get("status")
    page_number = request.GET.get("page")

    tenants_qs = get_tenants_for_user(
        user=request.user,
        search_query=search_query,
        status=status
    )

    paginator = Paginator(tenants_qs, 10) # 10 per page
    page_obj = paginator.get_page(page_number)

    context = {
        "tenants": page_obj,
        "page_obj": page_obj,
    }

    # HTMX request
    if request.headers.get("HX-Request"):
        return render(request, "tenants/partials/tenant_table_rows.html", context)

    return render(request, "tenants/tenant_list.html", context)