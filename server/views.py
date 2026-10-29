from django.shortcuts import render
from django.views.decorators.http import require_GET

from smuhammad.models import Property, PropertyCategory, PropertyStatus


@require_GET
def home(request):
    properties = Property.objects.filter(status=PropertyStatus.APPROVED).select_related('location', 'category', 'owner').prefetch_related('images')
    return render(request, 'home.html', {
        'properties': properties[:6],
        'property_count': properties.count(),
        'categories': PropertyCategory.objects.all(),
    })
