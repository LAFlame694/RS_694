from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator

from tenants.models import Tenant
from .models import Property, Unit
from tenants.choices import TenancyStatus
from .forms import AssignTenantForm, EditUnitForm, UnitForm

from .services.property_service import get_properties_for_user, get_property_stats
from .services.unit_service import (
    get_property_with_units, 
    get_units_stats, 
    assign_tenant_to_unit, 
    vacate_unit, 
    delete_unit,
    update_unit,
    get_unit_details,
    create_unit,
)

# Create your views here.
@login_required
def add_unit(request, property_id):
    property = get_object_or_404(Property, id=property_id)

    if request.method == 'POST':
        form = UnitForm(request.POST)

        if form.is_valid():
            try:
                unit = create_unit(
                    property=property,
                    unit_number=form.cleaned_data['unit_number'],
                    unit_type=form.cleaned_data['unit_type'],
                    floor=form.cleaned_data['floor']
                )
                messages.success(request, f'Unit {unit.unit_number} created successfully.')
                return redirect("unit_detail", unit_id=unit.id)
            
            except ValidationError as e:
                form.add_error('unit_number', e.message)
            
            except Exception:
                messages.error(request, "Something went wrong. Try again.")
    else:
        form = UnitForm()
    
    return render(request, 'properties/add_unit.html', {
        'form': form,
        'property': property
    })

@login_required
def unit_detail(request, unit_id):
    data = get_unit_details(unit_id)

    return render(request, 'properties/unit_detail.html', data)

@login_required
def edit_unit(request, unit_id):
    unit = get_object_or_404(Unit, id=unit_id)

    if request.method == 'POST':
        form = EditUnitForm(request.POST, instance=unit)

        if form.is_valid():
            try:
                update_unit(unit, **form.cleaned_data)

                messages.success(request, f'Unit {unit.unit_number} updated successfully.')
                return redirect('property_units', property_id=unit.property.id)
            
            except Exception as e:
                messages.error(request, f"Something went wrong. Please try again. {str(e)}")
    else:
        form = EditUnitForm(instance=unit)
    
    return render(request, 'properties/edit_unit.html', {
        'form': form,
        'unit': unit
    })

@login_required
def delete_unit_view(request, unit_id):
    unit = get_object_or_404(Unit, id=unit_id)

    if request.method == 'POST':
        try:
            delete_unit(unit)
            messages.success(request, "Unit deleted successfully.")
            return redirect('property_units', property_id=unit.property.id)
        
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect('property_units', property_id=unit.property.id)
        
    return render(request, 'properties/confirm_delete_unit.html', {'unit': unit})

@login_required
def assign_tenant(request, unit_id):
    unit = get_object_or_404(Unit, id=unit_id)

    available_tenants = Tenant.objects.filter(
        is_active=True
    ).exclude(
        tenancies__status=TenancyStatus.ACTIVE
    )

    if request.method == 'POST':
        form = AssignTenantForm(request.POST, available_tenants=available_tenants)

        if form.is_valid():
            try:
                assign_tenant_to_unit(
                    unit=unit,
                    tenant=form.cleaned_data['tenant'],
                    rent_amount=form.cleaned_data['rent_amount'],
                    start_date=form.cleaned_data['start_date'],
                    created_by=request.user
                )

                messages.success(request, f'Tenant assigned to {unit}.')
                return redirect('property_units', property_id=unit.property.id)

            except ValidationError as e:
                form.add_error(None, e.message)

    else:
        form = AssignTenantForm(available_tenants=available_tenants)

    return render(request, 'properties/assign_tenant.html', {
        'unit': unit,
        'form': form
    })

@login_required
def vacate_unit_view(request, unit_id):
    unit = get_object_or_404(Unit, id=unit_id)
    try:
        vacate_unit(unit)
        messages.success(request, f'{unit} has been vacated.')
    except Exception as e:
        messages.error(request, str(e))
    return redirect(request.META.get('HTTP_REFERER'))

@login_required
def property_list(request):
    properties = get_properties_for_user(request.user)
    stats = get_property_stats(request.user)

    context = {
        'properties': properties,
        'stats': stats,
    }

    return render(request, 'properties/property_list.html', context)

@login_required
def property_units(request, property_id):
    status = request.GET.get("status")
    search = request.GET.get("q")

    property, units = get_property_with_units(
        request.user,
        property_id,
        status=status,
        search=search
    )

    if not property:
        return redirect('property_list')
    
    # pagination
    paginator = Paginator(units, 10) # 10 units per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    stats = get_units_stats(units)

    context = {
        'property': property,
        'units': page_obj,
        'page_obj': page_obj,
        'stats': stats,
        'selected_status': status or 'ALL'
    }

    # HTMX request
    if request.headers.get('HX-Request'):
        return render(request, 'properties/partials/units_table.html', context)

    return render(request, 'properties/property_units.html', context)