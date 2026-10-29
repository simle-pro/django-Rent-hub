from django.conf import settings
from django.db import models


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorites')
    property = models.ForeignKey('smuhammad.Property', on_delete=models.CASCADE, related_name='favorites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Избранное объявление'
        verbose_name_plural = 'Избранные объявления'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'property'], name='unique_favorite_user_property'),
        ]

    def __str__(self):
        return f'{self.user} — {self.property}'


class Booking(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Ожидает подтверждения'),
        (STATUS_APPROVED, 'Подтверждена'),
        (STATUS_REJECTED, 'Отклонена'),
        (STATUS_CANCELLED, 'Отменена'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings')
    property = models.ForeignKey('smuhammad.Property', on_delete=models.CASCADE, related_name='bookings')
    start_date = models.DateField('Дата начала')
    end_date = models.DateField('Дата окончания')
    status = models.CharField('Статус', max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField('Создана', auto_now_add=True)

    class Meta:
        verbose_name = 'Заявка на аренду'
        verbose_name_plural = 'Заявки на аренду'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(start_date__lt=models.F('end_date')), name='booking_valid_date_range'),
        ]

    def __str__(self):
        return f'{self.property_id}: {self.start_date} — {self.end_date}'

    @staticmethod
    def has_approved_overlap(property_obj, start_date, end_date, exclude_pk=None):
        queryset = Booking.objects.filter(
            property=property_obj,
            status=Booking.STATUS_APPROVED,
            start_date__lt=end_date,
            end_date__gt=start_date,
        )
        if exclude_pk is not None:
            queryset = queryset.exclude(pk=exclude_pk)
        return queryset.exists()
