from django.conf import settings
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
