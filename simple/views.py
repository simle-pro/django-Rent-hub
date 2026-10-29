from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from firuz.models import Amenity, Property

from .forms import BookingForm, SearchForm, SORT_DIRECTIONS
from .models import Booking, Favorite

LOGIN_URL = 'firuz:login'


def _is_tenant(user):
    profile = getattr(user, 'profile', None)
    return profile is not None and profile.role == 'tenant'


@require_GET
def search(request):
    form = SearchForm(request.GET or None)
    queryset = (
        Property.objects.filter(status='approved')
        .select_related('location', 'category', 'owner')
        .prefetch_related('amenities')
    )
    if form.is_valid():
        q = form.cleaned_data.get('q')
        if q:
            queryset = queryset.filter(Q(title__icontains=q) | Q(location__name__icontains=q))
        min_price = form.cleaned_data.get('min_price')
        if min_price is not None:
            queryset = queryset.filter(price__gte=min_price)
        max_price = form.cleaned_data.get('max_price')
        if max_price is not None:
            queryset = queryset.filter(price__lte=max_price)
        category = form.cleaned_data.get('category')
        if category is not None:
            queryset = queryset.filter(category_id=category)
        for amenity_id in form.amenity_ids:
            queryset = queryset.filter(amenities__id=amenity_id)
        if form.amenity_ids:
            queryset = queryset.distinct()
        sort = form.cleaned_data.get('sort')
        queryset = queryset.order_by(SORT_DIRECTIONS.get(sort, '-created_at'))
    else:
        queryset = queryset.order_by('-created_at')
    page_obj = Paginator(queryset, 10).get_page(request.GET.get('page'))
    if request.user.is_authenticated:
        favorite_ids = set(request.user.favorites.values_list('property_id', flat=True))
    else:
        favorite_ids = set()
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'simple/search_results.html', {
        'form': form,
        'page_obj': page_obj,
        'favorite_ids': favorite_ids,
        'amenities': Amenity.objects.all().order_by('pk'),
        'search_querystring': params.urlencode(),
    })


@login_required(login_url=LOGIN_URL)
@require_POST
def favorite_toggle(request, property_id):
    property_obj = get_object_or_404(Property, pk=property_id)
    favorite = Favorite.objects.filter(user=request.user, property=property_obj).first()
    if favorite is not None:
        favorite.delete()
        messages.success(request, 'Объект удалён из избранного.')
    else:
        if property_obj.status != 'approved':
            raise Http404
        Favorite.objects.get_or_create(user=request.user, property=property_obj)
        messages.success(request, 'Объект добавлен в избранное.')
    next_url = request.POST.get('next', '')
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
        return redirect(next_url)
    return redirect('simple:favorite_list')


@login_required(login_url=LOGIN_URL)
@require_GET
def favorite_list(request):
    favorites = Favorite.objects.filter(user=request.user).select_related(
        'property', 'property__location', 'property__category', 'property__owner'
    ).prefetch_related('property__amenities')
    return render(request, 'simple/favorite_list.html', {'favorites': favorites})


@login_required(login_url=LOGIN_URL)
@require_http_methods(['GET', 'POST'])
def booking_create(request, property_id):
    if not _is_tenant(request.user):
        messages.error(request, 'Заявку может создать только арендатор.')
        return redirect('firuz:profile')
    property_obj = get_object_or_404(Property, pk=property_id, status='approved')
    if property_obj.owner_id == request.user.pk:
        messages.error(request, 'Нельзя подать заявку на собственное объявление.')
        return redirect('simple:search')
    form = BookingForm(request.POST or None, property_obj=property_obj)
    if request.method == 'POST' and form.is_valid():
        booking = form.save(commit=False)
        booking.user = request.user
        booking.property = property_obj
        booking.save()
        messages.success(request, 'Заявка отправлена владельцу.')
        return redirect('simple:booking_detail', pk=booking.pk)
    return render(request, 'simple/booking_form.html', {'form': form, 'property_obj': property_obj})


@login_required(login_url=LOGIN_URL)
@require_GET
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).select_related(
        'property', 'property__location', 'property__owner'
    )
    return render(request, 'simple/my_bookings.html', {'bookings': bookings})


@login_required(login_url=LOGIN_URL)
@require_GET
def booking_detail(request, pk):
    booking = get_object_or_404(Booking.objects.select_related(
        'property', 'property__location', 'property__category', 'property__owner'
    ), pk=pk)
    if booking.user_id != request.user.pk and booking.property.owner_id != request.user.pk:
        raise Http404
    can_approve = booking.property.owner_id == request.user.pk and booking.status == Booking.STATUS_PENDING
    can_cancel = booking.user_id == request.user.pk and booking.status in (
        Booking.STATUS_PENDING, Booking.STATUS_APPROVED,
    )
    return render(request, 'simple/booking_detail.html', {
        'booking': booking,
        'can_approve': can_approve,
        'can_cancel': can_cancel,
    })


@login_required(login_url=LOGIN_URL)
@require_POST
def booking_cancel(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if booking.status not in (Booking.STATUS_PENDING, Booking.STATUS_APPROVED):
        messages.error(request, 'Эту заявку нельзя отменить.')
        return redirect('simple:booking_detail', pk=pk)
    booking.status = Booking.STATUS_CANCELLED
    booking.save(update_fields=['status'])
    messages.success(request, 'Заявка отменена.')
    return redirect('simple:my_bookings')


@login_required(login_url=LOGIN_URL)
@require_GET
def received_bookings(request):
    bookings = Booking.objects.filter(property__owner=request.user).select_related(
        'property', 'property__location', 'user'
    )
    return render(request, 'simple/received_bookings.html', {'bookings': bookings})


@login_required(login_url=LOGIN_URL)
@require_POST
def booking_approve(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if booking.property.owner_id != request.user.pk:
        raise Http404
    with transaction.atomic():
        property_obj = Property.objects.select_for_update().get(pk=booking.property_id)
        booking = Booking.objects.select_for_update().get(pk=pk)
        if booking.status != Booking.STATUS_PENDING:
            messages.error(request, 'Подтвердить можно только ожидающую заявку.')
        elif Booking.has_approved_overlap(property_obj, booking.start_date, booking.end_date, exclude_pk=booking.pk):
            messages.error(request, 'Нельзя подтвердить: даты пересекаются с другой подтверждённой заявкой.')
        else:
            booking.status = Booking.STATUS_APPROVED
            booking.save(update_fields=['status'])
            messages.success(request, 'Заявка подтверждена.')
    return redirect('simple:booking_detail', pk=pk)


@login_required(login_url=LOGIN_URL)
@require_POST
def booking_reject(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if booking.property.owner_id != request.user.pk:
        raise Http404
    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=pk)
        if booking.status != Booking.STATUS_PENDING:
            messages.error(request, 'Отклонить можно только ожидающую заявку.')
        else:
            booking.status = Booking.STATUS_REJECTED
            booking.save(update_fields=['status'])
            messages.success(request, 'Заявка отклонена.')
    return redirect('simple:booking_detail', pk=pk)
