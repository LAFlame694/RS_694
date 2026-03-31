from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib import messages

from tenants.models import Tenant
from .models import Property, Unit

from .services.property_service import get_properties_for_user, get_property_stats
from .services.unit_service import get_property_with_units, get_units_stats, assign_tenant_to_unit, vacate_unit

# Create your views here.
@login_required
def assign_tenant(request, unit_id):
    unit = get_object_or_404(Unit, id=unit_id)

    if request.method == 'POST':
        tenant_id = request.POST.get('tenant_id')
        tenant = get_object_or_404(Tenant, id=tenant_id)
        try:
            assign_tenant_to_unit(unit, tenant, request.user)
            messages.success(request, f'{tenant} assigned to {unit}.')
        except Exception as e:
            messages.error(request, str(e))
        
        return redirect(request.META.get('HTTP_REFERER'))
    
    # For GET request, show tenant selection form
    available_tenants = Tenant.objects.filter(is_active=True)
    return render(request, 'properties/assign_tenant.html', {
        'unit': unit,
        'tenants': available_tenants
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
    property, units = get_property_with_units(request.user, property_id)

    if not property:
        return render('property_list') # safety fallback
    
    stats = get_units_stats(units)

    context = {
        'property': property,
        'units': units,
        'stats': stats,
    }

    return render(request, 'properties/property_units.html', context)