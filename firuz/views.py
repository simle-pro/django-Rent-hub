from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_http_methods, require_POST, require_GET

from smuhammad.models import Property, PropertyStatus

from .forms import ProfileForm, RegisterForm, UserForm, ReviewForm, ReportForm, RejectForm, ResolutionForm
from .models import Profile, Review, PropertyReport


@require_http_methods(['GET', 'POST'])
def register_user(request):
    if request.user.is_authenticated:
        return redirect('firuz:profile')
    form = RegisterForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            user.profile.role = form.cleaned_data['role']
            user.profile.save()
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = request.build_absolute_uri(reverse('firuz:activate', kwargs={'uidb64': uid, 'token': token}))
            send_mail('Подтверждение email RentHub', f'Подтвердите email по ссылке:\n{link}', settings.DEFAULT_FROM_EMAIL, [user.email])
        messages.success(request, 'Письмо подтверждения отправлено. Откройте ссылку из письма.')
        return redirect('firuz:login')
    return render(request, 'firuz/accounts/register.html', {'form': form})


@require_http_methods(['GET', 'POST'])
def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        if not uid.isdecimal() or len(uid) > 19:
            raise ValueError
        user = get_user_model().objects.get(pk=uid, is_active=False)
    except (ValueError, UnicodeError, OverflowError, get_user_model().DoesNotExist):
        return render(request, 'firuz/accounts/activate.html', {'invalid': True}, status=400)
    if not default_token_generator.check_token(user, token):
        return render(request, 'firuz/accounts/activate.html', {'invalid': True}, status=400)
    if request.method == 'POST':
        user.is_active = True
        user.save(update_fields=['is_active'])
        messages.success(request, 'Email подтверждён. Теперь можно войти.')
        return redirect('firuz:login')
    return render(request, 'firuz/accounts/activate.html')


@require_http_methods(['GET', 'POST'])
def login_user(request):
    if request.user.is_authenticated:
        return redirect('firuz:profile')
    form = AuthenticationForm(request, data=request.POST if request.method == 'POST' else None)
    next_url = request.POST.get('next', request.GET.get('next', ''))
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}, require_https=request.is_secure()):
            return redirect(next_url)
        return redirect('firuz:profile')
    return render(request, 'firuz/accounts/login.html', {'form': form, 'next': next_url})


@login_required(login_url='firuz:login')
@require_POST
def logout_user(request):
    logout(request)
    return redirect('firuz:login')


@login_required(login_url='firuz:login')
@require_GET
def profile(request):
    user_profile = get_object_or_404(Profile, user=request.user)
    return render(request, 'firuz/accounts/profile.html', {
        'profile': user_profile,
        'is_moderator': request.user.has_perm('firuz.moderate_property'),
        'reviews': Review.objects.filter(user=request.user).select_related('property')[:10],
        'reports': PropertyReport.objects.filter(user=request.user).select_related('property')[:10],
    })


@login_required(login_url='firuz:login')
@require_http_methods(['GET', 'POST'])
def profile_edit(request):
    user_profile = get_object_or_404(Profile, user=request.user)
    data = request.POST if request.method == 'POST' else None
    form = ProfileForm(data, instance=user_profile)
    user_form = UserForm(data, instance=request.user)
    if request.method == 'POST' and form.is_valid() and user_form.is_valid():
        with transaction.atomic():
            user_form.save()
            form.save()
        messages.success(request, 'Профиль сохранён.')
        return redirect('firuz:profile')
    return render(request, 'firuz/accounts/profile_edit.html', {'form': form, 'user_form': user_form})


@require_GET
def public_profile(request, pk):
    owner = get_object_or_404(get_user_model(), pk=pk, is_active=True, profile__role='owner')
    properties = Property.objects.filter(owner=owner, status=PropertyStatus.APPROVED).select_related('location', 'category')
    return render(request, 'firuz/accounts/public_profile.html', {
        'owner': owner, 'profile': owner.profile,
        'page_obj': Paginator(properties, 12).get_page(request.GET.get('page')),
    })


@require_GET
def review_list(request):
    properties = Property.objects.filter(status=PropertyStatus.APPROVED).select_related('owner', 'location')
    return render(request, 'firuz/reviews/review_list.html', {
        'page_obj': Paginator(properties, 12).get_page(request.GET.get('page')),
    })


@require_GET
def property_reviews(request, property_id):
    property_obj = get_object_or_404(Property.objects.select_related('owner'), pk=property_id, status=PropertyStatus.APPROVED)
    reviews = Review.objects.filter(property=property_obj).select_related('user')
    can_review = False
    if request.user.is_authenticated:
        can_review = (
            request.user.profile.role == 'tenant'
            and property_obj.owner_id != request.user.pk
            and not reviews.filter(user=request.user).exists()
        )
    return render(request, 'firuz/reviews/property_reviews.html', {
        'property': property_obj, 'form': ReviewForm(), 'can_review': can_review,
        'average_rating': reviews.aggregate(value=Avg('rating'))['value'],
        'page_obj': Paginator(reviews, 10).get_page(request.GET.get('page')),
    })


@login_required(login_url='firuz:login')
@require_POST
def review_create(request, property_id):
    property_obj = get_object_or_404(Property, pk=property_id, status=PropertyStatus.APPROVED)
    if property_obj.owner_id == request.user.pk or request.user.profile.role != 'tenant':
        raise PermissionDenied
    form = ReviewForm(request.POST)
    if form.is_valid():
        try:
            with transaction.atomic():
                review = form.save(commit=False)
                review.user = request.user
                review.property = property_obj
                review.save()
        except IntegrityError:
            form.add_error(None, 'Вы уже оставили отзыв об этом объявлении.')
        else:
            messages.success(request, 'Отзыв добавлен.')
            return redirect('firuz:property_reviews', property_id=property_obj.pk)
    return render(request, 'firuz/reviews/review_form.html', {'form': form, 'property': property_obj}, status=400)


@login_required(login_url='firuz:login')
@require_POST
def review_delete(request, pk):
    review = get_object_or_404(Review, pk=pk, user=request.user)
    property_id = review.property_id
    published = review.property.status == PropertyStatus.APPROVED
    review.delete()
    messages.success(request, 'Отзыв удалён.')
    if published:
        return redirect('firuz:property_reviews', property_id=property_id)
    return redirect('firuz:profile')


@login_required(login_url='firuz:login')
@permission_required('firuz.moderate_property', raise_exception=True)
@require_GET
def pending_properties(request):
    properties = Property.objects.filter(status=PropertyStatus.PENDING).exclude(owner=request.user).select_related('owner', 'location', 'category')
    return render(request, 'firuz/moderation/pending_properties.html', {
        'page_obj': Paginator(properties, 10).get_page(request.GET.get('page')),
    })


@login_required(login_url='firuz:login')
@permission_required('firuz.moderate_property', raise_exception=True)
@require_POST
def property_approve(request, pk):
    with transaction.atomic():
        property_obj = get_object_or_404(Property.objects.select_for_update(), pk=pk, status=PropertyStatus.PENDING)
        if property_obj.owner_id == request.user.pk:
            raise PermissionDenied
        property_obj.status = PropertyStatus.APPROVED
        property_obj.moderation_reason = ''
        property_obj.save(update_fields=['status', 'moderation_reason', 'updated_at'])
    messages.success(request, 'Объявление опубликовано.')
    return redirect('firuz:pending_properties')


@login_required(login_url='firuz:login')
@permission_required('firuz.moderate_property', raise_exception=True)
@require_POST
def property_reject(request, pk):
    with transaction.atomic():
        property_obj = get_object_or_404(Property.objects.select_for_update(), pk=pk, status=PropertyStatus.PENDING)
        if property_obj.owner_id == request.user.pk:
            raise PermissionDenied
        form = RejectForm(request.POST)
        if form.is_valid():
            property_obj.status = PropertyStatus.REJECTED
            property_obj.moderation_reason = form.cleaned_data['reason']
            property_obj.save(update_fields=['status', 'moderation_reason', 'updated_at'])
            messages.success(request, 'Объявление отклонено.')
            return redirect('firuz:pending_properties')
    return render(request, 'firuz/moderation/reject_form.html', {'form': form, 'property': property_obj}, status=400)


@login_required(login_url='firuz:login')
@require_http_methods(['GET', 'POST'])
def report_create(request, property_id):
    property_obj = get_object_or_404(Property, pk=property_id, status=PropertyStatus.APPROVED)
    if property_obj.owner_id == request.user.pk:
        raise PermissionDenied
    form = ReportForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                report = form.save(commit=False)
                report.user = request.user
                report.property = property_obj
                report.save()
        except IntegrityError:
            form.add_error(None, 'Ваша жалоба на это объявление уже рассматривается.')
        else:
            messages.success(request, 'Жалоба отправлена на рассмотрение.')
            return redirect('firuz:profile')
    return render(request, 'firuz/moderation/report_form.html', {'form': form, 'property': property_obj})


@login_required(login_url='firuz:login')
@permission_required('firuz.moderate_property', raise_exception=True)
@require_GET
def property_reports(request):
    reports = PropertyReport.objects.exclude(property__owner=request.user).select_related('user', 'property', 'resolved_by')
    return render(request, 'firuz/moderation/property_reports.html', {
        'page_obj': Paginator(reports, 10).get_page(request.GET.get('page')),
    })


@login_required(login_url='firuz:login')
@permission_required('firuz.moderate_property', raise_exception=True)
@require_POST
def report_resolve(request, pk):
    report = get_object_or_404(PropertyReport, pk=pk)
    with transaction.atomic():
        property_obj = get_object_or_404(Property.objects.select_for_update(), pk=report.property_id)
        report = get_object_or_404(PropertyReport.objects.select_for_update(), pk=pk, status='pending')
        if property_obj.owner_id == request.user.pk:
            raise PermissionDenied
        form = ResolutionForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['hide_property'] and property_obj.status != PropertyStatus.APPROVED:
                form.add_error('hide_property', 'Скрыть можно только опубликованное объявление.')
            else:
                if form.cleaned_data['hide_property']:
                    property_obj.status = PropertyStatus.HIDDEN
                    property_obj.save(update_fields=['status', 'updated_at'])
                report.status = 'resolved'
                report.resolution = form.cleaned_data['resolution']
                report.resolved_by = request.user
                report.resolved_at = timezone.now()
                report.save(update_fields=['status', 'resolution', 'resolved_by', 'resolved_at'])
                messages.success(request, 'Жалоба рассмотрена.')
                return redirect('firuz:property_reports')
    return render(request, 'firuz/moderation/resolution_form.html', {'form': form, 'report': report}, status=400)
