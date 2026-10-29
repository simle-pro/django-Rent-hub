from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse


class PropertyCategory(models.Model):
    """Категория объявления: квартира, дом, студия и т.д."""

    name = models.CharField('название', max_length=100, unique=True)
    description = models.TextField('описание', blank=True)

    class Meta:
        verbose_name = 'категория недвижимости'
        verbose_name_plural = 'Категории недвижимости'
        ordering = ['name']

    def __str__(self):
        return self.name


class Location(models.Model):
    """Местоположение объекта недвижимости."""

    city = models.CharField('город', max_length=100)
    address = models.CharField('адрес', max_length=255)
    description = models.TextField('описание района', blank=True)

    class Meta:
        verbose_name = 'местоположение'
        verbose_name_plural = 'Местоположения'
        ordering = ['city', 'address']

    def __str__(self):
        return f'{self.city}, {self.address}'


class Amenity(models.Model):
    """Удобство: Wi-Fi, парковка, кондиционер и т.д."""

    name = models.CharField('название', max_length=100, unique=True)
    description = models.TextField('описание', blank=True)

    class Meta:
        verbose_name = 'удобство'
        verbose_name_plural = 'Удобства'
        ordering = ['name']

    def __str__(self):
        return self.name


class PropertyStatus(models.TextChoices):
    """Статусы объявления и правила их переходов (контракт между участниками)."""

    DRAFT = 'draft', 'Черновик'
    PENDING = 'pending', 'На модерации'
    APPROVED = 'approved', 'Опубликовано'
    REJECTED = 'rejected', 'Отклонено'
    HIDDEN = 'hidden', 'Скрыто'


class Property(models.Model):
    """Объявление о недвижимости: создал владелец, публикует модератор."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='владелец',
        related_name='owned_properties',
    )
    title = models.CharField('заголовок', max_length=200)
    description = models.TextField('описание')
    price = models.DecimalField(
        'цена за сутки',
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Цена за сутки в рублях, только положительное число',
    )
    category = models.ForeignKey(
        PropertyCategory,
        on_delete=models.PROTECT,
        verbose_name='категория',
        related_name='properties',
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        verbose_name='местоположение',
        related_name='properties',
    )
    amenities = models.ManyToManyField(
        Amenity,
        verbose_name='удобства',
        blank=True,
        related_name='properties',
    )
    status = models.CharField(
        'статус',
        max_length=10,
        choices=PropertyStatus.choices,
        default=PropertyStatus.DRAFT,
    )
    moderation_reason = models.TextField(
        'причина отклонения',
        blank=True,
        help_text='Заполняет только модератор при отклонении объявления',
    )
    created_at = models.DateTimeField('создано', auto_now_add=True)
    updated_at = models.DateTimeField('обновлено', auto_now=True)

    class Meta:
        verbose_name = 'объявление'
        verbose_name_plural = 'Объявления'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gt=0),
                name='property_price_must_be_positive',
            ),
        ]
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return self.title

    @property
    def is_public(self):
        """Опубликованное объявление видно гостям и поиску."""
        return self.status == PropertyStatus.APPROVED

    def get_absolute_url(self):
        return reverse('smuhammad:property_detail', kwargs={'pk': self.pk})


class PropertyImage(models.Model):
    """Фотография объявления."""

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        verbose_name='объявление',
        related_name='images',
    )
    image = models.ImageField('фотография', upload_to='properties/images/%Y/%m/')
    created_at = models.DateTimeField('добавлено', auto_now_add=True)

    class Meta:
        verbose_name = 'фотография объявления'
        verbose_name_plural = 'Фотографии объявлений'
        ordering = ['created_at']

    def __str__(self):
        return f'Фото #{self.pk} — {self.property.title}'


@receiver(post_delete, sender=PropertyImage)
def delete_property_image_file(sender, instance, **kwargs):
    """Удаляет файл фотографии с диска вместе с записью в базе."""
    if instance.image:
        instance.image.delete(save=False)
