from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import MAX_IMAGES_PER_PROPERTY, PropertyForm, PropertyImagesForm, LocationForm
from .models import Property, PropertyCategory, PropertyImage, PropertyStatus

LOGIN_URL = 'firuz:login'


class PropertyListView(ListView):
    """Каталог: гостям и поиску доступны только опубликованные объявления."""

    model = Property
    template_name = 'smuhammad/property_list.html'
    context_object_name = 'properties'
    paginate_by = 9

    def get_queryset(self):
        queryset = (
            Property.objects.select_related('owner', 'category', 'location')
            .prefetch_related('images', 'amenities')
            .filter(status=PropertyStatus.APPROVED)
        )
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(location__city__icontains=query)
                | Q(location__address__icontains=query)
            )
        category_id = self.request.GET.get('category')
        if category_id and category_id.isdigit():
            queryset = queryset.filter(category_id=category_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '').strip()
        context['selected_category'] = self.request.GET.get('category', '')
        context['categories'] = PropertyCategory.objects.all()
        return context


class PropertyDetailView(DetailView):
    """Страница объявления: непубличное видно только владельцу и модератору."""

    model = Property
    template_name = 'smuhammad/property_detail.html'
    context_object_name = 'property'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_favorite'] = self.request.user.is_authenticated and self.object.favorites.filter(user=self.request.user).exists()
        return context

    def get_queryset(self):
        queryset = Property.objects.select_related(
            'owner', 'category', 'location'
        ).prefetch_related('amenities', 'images')
        user = self.request.user
        if user.is_authenticated and user.has_perm('firuz.moderate_property'):
            return queryset
        if user.is_authenticated:
            return queryset.filter(Q(status=PropertyStatus.APPROVED) | Q(owner=user))
        return queryset.filter(status=PropertyStatus.APPROVED)


class PropertyCreateView(LoginRequiredMixin, CreateView):
    """Создание объявления: доступно только авторизованным владельцам."""

    model = Property
    form_class = PropertyForm
    template_name = 'smuhammad/property_form.html'
    login_url = LOGIN_URL

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.profile.role != 'owner':
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        location = self.request.GET.get('location', '')
        if location.isdecimal() and len(location) < 19:
            initial['location'] = location
        return initial

    def form_valid(self, form):
        property_obj = form.save(commit=False)
        property_obj.owner = self.request.user
        property_obj.status = PropertyStatus.DRAFT
        property_obj.save()
        form.save_m2m()
        messages.success(
            self.request,
            'Объявление сохранено как черновик. Добавьте фотографии и отправьте на модерацию.',
        )
        return redirect('smuhammad:property_images', pk=property_obj.pk)


class PropertyUpdateView(LoginRequiredMixin, UpdateView):
    """Правка своего объявления: опубликованное уходит на повторную модерацию."""

    model = Property
    form_class = PropertyForm
    template_name = 'smuhammad/property_form.html'
    context_object_name = 'property'
    login_url = LOGIN_URL

    def get_queryset(self):
        return Property.objects.filter(owner=self.request.user)

    def form_valid(self, form):
        property_obj = form.save(commit=False)
        if property_obj.status == PropertyStatus.APPROVED:
            property_obj.status = PropertyStatus.PENDING
            messages.info(
                self.request,
                'Опубликованное объявление отправлено на повторную модерацию.',
            )
        property_obj.save()
        form.save_m2m()
        messages.success(self.request, 'Изменения сохранены.')
        return redirect(property_obj.get_absolute_url())


class PropertyDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление: GET только показывает подтверждение, удаляет POST."""

    model = Property
    template_name = 'smuhammad/property_confirm_delete.html'
    context_object_name = 'property'
    success_url = reverse_lazy('smuhammad:my_properties')
    login_url = LOGIN_URL

    def get_queryset(self):
        return Property.objects.filter(owner=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Объявление удалено.')
        return super().form_valid(form)


class MyPropertiesListView(LoginRequiredMixin, ListView):
    """Мои объявления: владелец видит свои записи во всех статусах."""

    model = Property
    template_name = 'smuhammad/my_properties.html'
    context_object_name = 'properties'
    paginate_by = 10
    login_url = LOGIN_URL

    def get_queryset(self):
        return (
            Property.objects.filter(owner=self.request.user)
            .select_related('category', 'location')
            .prefetch_related('images')
        )


@login_required(login_url=LOGIN_URL)
@require_POST
def submit_property(request, pk):
    """Отправка владельцем объявления на модерацию."""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user)
    allowed_statuses = (
        PropertyStatus.DRAFT,
        PropertyStatus.REJECTED,
        PropertyStatus.HIDDEN,
    )
    if property_obj.status not in allowed_statuses:
        messages.error(request, 'Это объявление уже на модерации или опубликовано.')
    else:
        property_obj.status = PropertyStatus.PENDING
        property_obj.moderation_reason = ''
        property_obj.save(update_fields=['status', 'moderation_reason', 'updated_at'])
        messages.success(request, 'Объявление отправлено на модерацию.')
    return redirect('smuhammad:property_detail', pk=property_obj.pk)


@login_required(login_url=LOGIN_URL)
@require_POST
def hide_property(request, pk):
    """Владелец скрывает своё объявление из каталога."""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user)
    if property_obj.status not in (PropertyStatus.APPROVED, PropertyStatus.PENDING):
        messages.error(request, 'Скрыть можно только опубликованное объявление.')
    else:
        property_obj.status = PropertyStatus.HIDDEN
        property_obj.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Объявление скрыто из каталога.')
    return redirect('smuhammad:property_detail', pk=property_obj.pk)


@login_required(login_url=LOGIN_URL)
def property_images(request, pk):
    """Страница управления фотографиями своего объявления."""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user)
    return render(
        request,
        'smuhammad/property_images.html',
        {
            'property': property_obj,
            'images': property_obj.images.all(),
            'form': PropertyImagesForm(),
            'max_images': MAX_IMAGES_PER_PROPERTY,
        },
    )


@login_required(login_url=LOGIN_URL)
@require_POST
def add_property_images(request, pk):
    """Загрузка нескольких фотографий с проверкой формы и файлов."""
    property_obj = get_object_or_404(Property, pk=pk, owner=request.user)
    form = PropertyImagesForm(request.POST, request.FILES)
    if not form.is_valid():
        error_text = ' '.join(
            ' '.join(errors) for errors in form.errors.values()
        )
        messages.error(request, f'Фотографии не загружены: {error_text}')
        return redirect('smuhammad:property_images', pk=property_obj.pk)

    images = form.cleaned_data['images']
    with transaction.atomic():
        property_obj = get_object_or_404(Property.objects.select_for_update(), pk=pk, owner=request.user)
        already_uploaded = property_obj.images.count()
        if already_uploaded + len(images) > MAX_IMAGES_PER_PROPERTY:
            messages.error(request, f'У объявления уже {already_uploaded} фото, не больше {MAX_IMAGES_PER_PROPERTY} на всё объявление.')
            return redirect('smuhammad:property_images', pk=property_obj.pk)
        for image in images:
            PropertyImage.objects.create(property=property_obj, image=image)
        if property_obj.status == PropertyStatus.APPROVED:
            property_obj.status = PropertyStatus.PENDING
            property_obj.save(update_fields=['status', 'updated_at'])
            messages.info(request, 'После изменения фотографий объявление отправлено на повторную модерацию.')
    messages.success(request, f'Добавлено фотографий: {len(images)}.')
    return redirect('smuhammad:property_images', pk=property_obj.pk)


@login_required(login_url=LOGIN_URL)
@require_POST
def delete_property_image(request, pk):
    """Удаление фотографии: чужое фото удалить нельзя."""
    image = get_object_or_404(PropertyImage, pk=pk, property__owner=request.user)
    property_pk = image.property_id
    with transaction.atomic():
        property_obj = get_object_or_404(Property.objects.select_for_update(), pk=property_pk, owner=request.user)
        image = get_object_or_404(PropertyImage, pk=pk, property=property_obj)
        image.delete()
        if property_obj.status == PropertyStatus.APPROVED:
            property_obj.status = PropertyStatus.PENDING
            property_obj.save(update_fields=['status', 'updated_at'])
            messages.info(request, 'После изменения фотографий объявление отправлено на повторную модерацию.')
    messages.success(request, 'Фотография удалена.')
    return redirect('smuhammad:property_images', pk=property_pk)


@login_required(login_url=LOGIN_URL)
@require_http_methods(['GET', 'POST'])
def location_create(request):
    if request.user.profile.role != 'owner':
        raise PermissionDenied
    form = LocationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        location = form.save()
        messages.success(request, 'Адрес добавлен. Теперь заполните объявление.')
        return redirect(reverse('smuhammad:property_create') + f'?location={location.pk}')
    return render(request, 'smuhammad/location_form.html', {'form': form})
