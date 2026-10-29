from datetime import timedelta
from io import BytesIO, StringIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from simple.models import Booking, Favorite
from smuhammad.models import Property, PropertyCategory, PropertyImage, Location


class SiteIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('owner')
        cls.owner.profile.role = 'owner'
        cls.owner.profile.save()
        cls.tenant = get_user_model().objects.create_user('tenant')
        cls.category = PropertyCategory.objects.create(name='Квартира')
        cls.location = Location.objects.create(city='Душанбе', address='Рудаки 10')
        cls.property = Property.objects.create(
            owner=cls.owner, title='Жильё у парка', description='Описание жилья',
            price='100', category=cls.category, location=cls.location, status='approved',
        )

    def make_booking(self):
        return Booking.objects.create(
            user=self.tenant, property=self.property,
            start_date=timezone.localdate() + timedelta(days=2),
            end_date=timezone.localdate() + timedelta(days=5),
        )

    def test_home_exists_and_does_not_expose_drafts(self):
        Property.objects.create(
            owner=self.owner, title='Закрытый черновик', description='Описание',
            price='100', category=self.category, location=self.location, status='draft',
        )
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Жильё у парка')
        self.assertNotContains(response, 'Закрытый черновик')
        self.assertEqual(response.context['property_count'], 1)

    def test_tenant_cannot_create_property_or_location(self):
        self.client.force_login(self.tenant)
        for name in ['property_create', 'location_create']:
            url = reverse('smuhammad:' + name)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {'city': 'Город', 'address': 'Адрес'}).status_code, 403)
        self.assertEqual(Property.objects.count(), 1)
        self.assertEqual(Location.objects.count(), 1)

    def test_owner_can_add_real_address_then_create_property(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('smuhammad:location_create'), {
            'city': 'Худжанд', 'address': 'улица Сомони 8', 'description': '',
        })
        location = Location.objects.get(city='Худжанд')
        self.assertRedirects(response, reverse('smuhammad:property_create') + f'?location={location.pk}')
        form_response = self.client.get(response.url)
        self.assertEqual(str(form_response.context['form'].initial['location']), str(location.pk))

    def test_reference_setup_is_repeatable_without_creating_fake_listings(self):
        call_command('init_renthub', stdout=StringIO())
        first_count = PropertyCategory.objects.count()
        call_command('init_renthub', stdout=StringIO())
        self.assertEqual(PropertyCategory.objects.count(), first_count)
        self.assertEqual(Property.objects.count(), 1)
        self.assertEqual(get_user_model().objects.count(), 2)

    def test_hidden_favorite_does_not_expose_description_or_link(self):
        Favorite.objects.create(user=self.tenant, property=self.property)
        self.property.status = 'hidden'
        self.property.save()
        self.client.force_login(self.tenant)
        response = self.client.get(reverse('simple:favorite_list'))
        self.assertContains(response, 'Объект больше не публикуется.')
        self.assertNotContains(response, self.property.title)
        self.assertNotContains(response, self.property.get_absolute_url())

    def test_owner_cannot_approve_hidden_or_expired_booking(self):
        booking = self.make_booking()
        self.client.force_login(self.owner)
        url = reverse('simple:booking_approve', args=[booking.pk])
        self.property.status = 'hidden'
        self.property.save()
        self.client.post(url)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'pending')
        self.property.status = 'approved'
        self.property.save()
        booking.start_date = timezone.localdate() - timedelta(days=1)
        booking.save()
        self.client.post(url)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'pending')

    def test_booking_date_range_is_protected_in_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Booking.objects.create(user=self.tenant, property=self.property, start_date=timezone.localdate(), end_date=timezone.localdate())

    def test_new_photos_require_moderation_again(self):
        image_data = BytesIO()
        Image.new('RGB', (20, 20), (100, 140, 90)).save(image_data, format='JPEG')
        image = SimpleUploadedFile('test.jpg', image_data.getvalue(), content_type='image/jpeg')
        self.client.force_login(self.owner)
        with TemporaryDirectory(prefix='renthub-photos-') as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(reverse('smuhammad:property_images_add', args=[self.property.pk]), {'images': [image]})
            self.assertEqual(response.status_code, 302)
            self.property.refresh_from_db()
            self.assertEqual(self.property.status, 'pending')
            self.assertEqual(PropertyImage.objects.filter(property=self.property).count(), 1)
            self.assertNotContains(self.client.get(reverse('home')), 'href="' + self.property.get_absolute_url() + '"')

    def test_deleting_published_photo_requires_moderation_again(self):
        self.client.force_login(self.owner)
        with TemporaryDirectory(prefix='renthub-photos-') as media_root, override_settings(MEDIA_ROOT=media_root):
            image = PropertyImage.objects.create(property=self.property, image='missing-test.jpg')
            self.client.post(reverse('smuhammad:property_image_delete', args=[image.pk]))
            self.property.refresh_from_db()
            self.assertEqual(self.property.status, 'pending')
            self.assertFalse(PropertyImage.objects.filter(pk=image.pk).exists())
