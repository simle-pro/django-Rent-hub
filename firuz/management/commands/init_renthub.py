from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from io import BytesIO
from urllib.request import Request, urlopen

from PIL import Image

from smuhammad.models import Amenity, PropertyCategory, Property, Location, PropertyImage


class Command(BaseCommand):
    help = 'Добавить категории и удобства; с --demo также демонстрационные объявления.'

    def add_arguments(self, parser):
        parser.add_argument('--demo', action='store_true', help='Дополнительно добавить демонстрационные объявления.')
        parser.add_argument('--photos', action='store_true', help='Добавить демо-объявления и скачать фотографии с Unsplash.')

    def handle(self, *args, **options):
        with transaction.atomic():
            for name in ['Квартира', 'Дом', 'Студия', 'Комната']:
                PropertyCategory.objects.get_or_create(name=name)
            for name in ['Wi-Fi', 'Парковка', 'Кондиционер', 'Кухня', 'Стиральная машина']:
                Amenity.objects.get_or_create(name=name)
            if options['demo'] or options['photos']:
                self.create_demo_properties()
        if options['photos']:
            self.add_demo_photos()
        self.stdout.write(self.style.SUCCESS('Категории и удобства готовы. Существующие данные сохранены.'))

    def create_demo_properties(self):
        owner, created = get_user_model().objects.get_or_create(
            username='renthub_demo_owner',
            defaults={'email': 'demo-owner@example.invalid', 'first_name': 'Демо', 'last_name': 'Владелец'},
        )
        if not created and owner.email != 'demo-owner@example.invalid':
            raise CommandError('Имя renthub_demo_owner уже занято другим пользователем.')
        if created:
            owner.set_unusable_password()
            owner.save(update_fields=['password'])
            owner.profile.role = 'owner'
            owner.profile.bio = 'Демонстрационный профиль RentHub. Объявления вымышлены и предназначены для проверки сайта.'
            owner.profile.save()
        listings = [
            ('Светлая квартира у парка', 'Квартира', 'Душанбе', 'Демо-адрес: район парка, 1', '3200.00', 'Две комнаты, отдельная кухня и балкон. Подходит для пары или небольшой семьи.', ['Wi-Fi', 'Кухня', 'Кондиционер'], 'approved'),
            ('Уютная студия в центре', 'Студия', 'Душанбе', 'Демо-адрес: центральный район, 2', '2200.00', 'Компактная студия с рабочим местом и оборудованной кухней.', ['Wi-Fi', 'Кухня', 'Стиральная машина'], 'approved'),
            ('Дом с садом для всей семьи', 'Дом', 'Гиссар', 'Демо-адрес: садовый квартал, 3', '6500.00', 'Просторный дом, три спальни, зелёный двор и место для автомобиля.', ['Wi-Fi', 'Парковка', 'Кухня', 'Стиральная машина'], 'approved'),
            ('Квартира с видом на город', 'Квартира', 'Худжанд', 'Демо-адрес: верхний квартал, 4', '2800.00', 'Двухкомнатная квартира с большой гостиной и светлой спальней.', ['Wi-Fi', 'Кондиционер', 'Кухня'], 'approved'),
            ('Тихая комната с рабочим местом', 'Комната', 'Душанбе', 'Демо-адрес: университетский район, 5', '1200.00', 'Отдельная комната для одного гостя. Общая кухня и удобное рабочее место.', ['Wi-Fi', 'Кухня', 'Стиральная машина'], 'approved'),
            ('Загородный дом у гор', 'Дом', 'Варзоб', 'Демо-адрес: загородный посёлок, 6', '9000.00', 'Дом для спокойных выходных: большая терраса, две спальни и парковка.', ['Парковка', 'Кухня', 'Кондиционер'], 'approved'),
            ('Новая квартира на модерации', 'Квартира', 'Душанбе', 'Демо-адрес: новый квартал, 7', '3500.00', 'Объявление для проверки одобрения и отклонения модератором.', ['Wi-Fi', 'Парковка'], 'pending'),
        ]
        added = 0
        for title, category, city, address, price, description, amenities, status in listings:
            location, _ = Location.objects.get_or_create(city=city, address=address)
            property_obj, created = Property.objects.get_or_create(
                owner=owner, title='[Демо] ' + title,
                defaults={
                    'category': PropertyCategory.objects.get(name=category),
                    'location': location, 'price': price, 'status': status,
                    'description': 'Демонстрационное объявление. Адрес и условия вымышлены.\n\n' + description,
                },
            )
            if created:
                property_obj.amenities.set(Amenity.objects.filter(name__in=amenities))
                added += 1
        self.stdout.write(self.style.SUCCESS(f'Добавлено демонстрационных объявлений: {added}. Существующие записи сохранены.'))

    def add_demo_photos(self):
        photos = {
            'Светлая квартира у парка': '1600210492486-724fe5c67fb0',
            'Уютная студия в центре': '1522708323590-d24dbb6b0267',
            'Дом с садом для всей семьи': '1564013799919-ab600027ffc6',
            'Квартира с видом на город': '1600607687920-4e2a09cf159d',
            'Тихая комната с рабочим местом': '1611892440504-42a792e24d32',
            'Загородный дом у гор': '1449158743715-0a90ebb6d2d8',
            'Новая квартира на модерации': '1502672260266-1c1ef2d93688',
        }
        added = 0
        for title, photo_id in photos.items():
            property_obj = Property.objects.filter(
                owner__username='renthub_demo_owner', owner__email='demo-owner@example.invalid', title='[Демо] ' + title,
            ).first()
            if property_obj is None or property_obj.images.exists():
                continue
            url = f'https://images.unsplash.com/photo-{photo_id}?auto=format&fit=crop&w=1400&q=80'
            try:
                cached = settings.MEDIA_ROOT / 'demo_sources' / f'{photo_id}.jpg'
                if cached.is_file():
                    data = cached.read_bytes()
                else:
                    request = Request(url, headers={'User-Agent': 'RentHub-demo/1.0'})
                    with urlopen(request, timeout=25) as response:
                        data = response.read(6 * 1024 * 1024 + 1)
                if len(data) > 6 * 1024 * 1024:
                    raise ValueError('Фотография слишком большая.')
                with Image.open(BytesIO(data)) as image:
                    image.verify()
                photo = PropertyImage(property=property_obj)
                photo.image.save(f'demo-{photo_id}.jpg', ContentFile(data), save=True)
                credit = f'Фото-иллюстрация: Unsplash. Это не фотография объекта по демо-адресу.\nИсточник: {url}'
                if 'Фото-иллюстрация: Unsplash.' not in property_obj.description:
                    property_obj.description += '\n\n' + credit
                    property_obj.save(update_fields=['description'])
                added += 1
            except (OSError, ValueError) as error:
                self.stderr.write(f'Не удалось добавить фото для «{title}»: {error}')
        self.stdout.write(self.style.SUCCESS(f'Добавлено фотографий: {added}.'))
