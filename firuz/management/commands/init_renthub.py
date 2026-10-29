from django.core.management.base import BaseCommand
from django.db import transaction

from smuhammad.models import Amenity, PropertyCategory


class Command(BaseCommand):
    help = 'Добавить начальные категории жилья и удобства без создания пользователей и объявлений.'

    @transaction.atomic
    def handle(self, *args, **options):
        for name in ['Квартира', 'Дом', 'Студия', 'Комната']:
            PropertyCategory.objects.get_or_create(name=name)
        for name in ['Wi-Fi', 'Парковка', 'Кондиционер', 'Кухня', 'Стиральная машина']:
            Amenity.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS('Категории и удобства готовы. Существующие данные сохранены.'))
