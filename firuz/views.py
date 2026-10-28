from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_http_methods, require_POST, require_GET

from .forms import ProfileForm, RegisterForm, UserForm
from .models import Profile


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
    return render(request, 'firuz/accounts/public_profile.html', {'owner': owner, 'profile': owner.profile})
