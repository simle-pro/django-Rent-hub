from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Profile(models.Model):
    ROLE_CHOICES = [
        ('tenant', 'Арендатор'),
        ('owner', 'Владелец'),
        ('moderator', 'Модератор'),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField('Роль', max_length=10, choices=ROLE_CHOICES, default='tenant')
    phone = models.CharField('Телефон', max_length=30, blank=True)
    bio = models.TextField('О себе', max_length=2000, blank=True)

    class Meta:
        permissions = [('moderate_property', 'Может модерировать объявления и жалобы')]

    def __str__(self):
        return self.user.get_username()


class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='property_reviews')
    property = models.ForeignKey('smuhammad.Property', on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField('Оценка', validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField('Отзыв', max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['user', 'property'], name='firuz_unique_property_review'),
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name='firuz_review_rating_range'),
        ]

    def __str__(self):
        return f'{self.user} — {self.property}: {self.rating}'


class PropertyReport(models.Model):
    REASON_CHOICES = [('fraud', 'Мошенничество'), ('incorrect', 'Неверные сведения'), ('other', 'Другое')]
    STATUS_CHOICES = [('pending', 'На рассмотрении'), ('resolved', 'Рассмотрена')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='property_reports')
    property = models.ForeignKey('smuhammad.Property', on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField('Причина', max_length=20, choices=REASON_CHOICES)
    text = models.TextField('Описание', max_length=2000)
    status = models.CharField('Статус', max_length=10, choices=STATUS_CHOICES, default='pending')
    resolution = models.TextField('Решение', max_length=2000, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_property_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['user', 'property'], condition=models.Q(status='pending'), name='firuz_unique_pending_report'),
        ]

    def __str__(self):
        return f'{self.property} — {self.get_reason_display()}'
