import shutil
import tempfile
from decimal import Decimal
from io import BytesIO

from PIL import Image
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from .forms import MAX_IMAGES_PER_PROPERTY
from .models import (
    Amenity,
    Location,
    Property,
    PropertyCategory,
    PropertyImage,
    PropertyStatus,
)

TEMP_MEDIA_ROOT = tempfile.mkdtemp(prefix='smuhammad_media_')


def tearDownModule():
    shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)


def make_image(name='photo.jpg', color=(200, 50, 50)):
    """Собирает настоящий JPEG, чтобы проверить загрузку через Pillow."""
    buffer = BytesIO()
    Image.new('RGB', (60, 60), color).save(buffer, format='JPEG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')


class PropertyTestCase(TestCase):
    """Общие данные: владелец, чужой пользователь, справочники."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user('owner', password='pass-12345')
        cls.other_user = User.objects.create_user('other', password='pass-12345')
        cls.category = PropertyCategory.objects.create(name='Квартира')
        cls.location = Location.objects.create(city='Ташкент', address='ул. Амира Темура, 1')
        cls.amenity = Amenity.objects.create(name='Wi-Fi')

    def create_property(self, owner=None, status=PropertyStatus.DRAFT, **kwargs):
        data = {
            'owner': owner or self.owner,
            'title': 'Сдам квартиру',
            'description': 'Светлая квартира рядом с парком',
            'price': '250.00',
            'category': self.category,
            'location': self.location,
            'status': status,
        }
        data.update(kwargs)
        return Property.objects.create(**data)

    def valid_form_data(self, **kwargs):
        data = {
            'title': 'Сдам студию',
            'description': 'Рядом с метро',
            'price': '300.00',
            'category': self.category.pk,
            'location': self.location.pk,
        }
        data.update(kwargs)
        return data


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PropertyVisibilityTests(PropertyTestCase):
    """Гость видит только опубликованное, чужие черновики не открыть."""

    def setUp(self):
        self.approved = self.create_property(status=PropertyStatus.APPROVED)
        self.draft = self.create_property(status=PropertyStatus.DRAFT, title='Черновик')
        self.pending = self.create_property(status=PropertyStatus.PENDING, title='Ожидает')
        self.rejected = self.create_property(status=PropertyStatus.REJECTED, title='Отклонено')
        self.hidden = self.create_property(status=PropertyStatus.HIDDEN, title='Скрыто')

    def test_guest_catalog_shows_only_approved(self):
        response = self.client.get(reverse('smuhammad:property_list'))
        self.assertEqual(response.status_code, 200)
        properties = list(response.context['properties'])
        self.assertEqual(properties, [self.approved])

    def test_catalog_is_paginated(self):
        for index in range(12):
            self.create_property(
                status=PropertyStatus.APPROVED, title=f'Объявление {index}'
            )
        response = self.client.get(reverse('smuhammad:property_list'))
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(len(response.context['properties']), 9)
        response = self.client.get(reverse('smuhammad:property_list') + '?page=2')
        self.assertEqual(len(response.context['properties']), 4)

    def test_guest_search_finds_only_approved(self):
        found = self.client.get(reverse('smuhammad:property_list'), {'q': 'Черновик'})
        self.assertNotIn(self.draft, list(found.context['properties']))
        found = self.client.get(reverse('smuhammad:property_list'), {'q': 'Сдам квартиру'})
        self.assertIn(self.approved, list(found.context['properties']))
        self.assertNotIn(self.pending, list(found.context['properties']))

    def test_catalog_filters_by_category(self):
        other_category = PropertyCategory.objects.create(name='Дом')
        house = self.create_property(
            status=PropertyStatus.APPROVED,
            title='Дом в предгорье',
            category=other_category,
        )
        response = self.client.get(
            reverse('smuhammad:property_list'), {'category': other_category.pk}
        )
        self.assertEqual(list(response.context['properties']), [house])
        response = self.client.get(
            reverse('smuhammad:property_list'), {'category': self.category.pk}
        )
        self.assertEqual(list(response.context['properties']), [self.approved])

    def test_owner_sees_rejection_reason_on_detail(self):
        self.rejected.moderation_reason = 'Не хватает фотографий'
        self.rejected.save()
        self.client.login(username='owner', password='pass-12345')
        response = self.client.get(
            reverse('smuhammad:property_detail', args=[self.rejected.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Не хватает фотографий')

    def test_guest_opens_only_approved_detail(self):
        url = reverse('smuhammad:property_detail', args=[self.approved.pk])
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_guest_gets_404_on_unpublished_detail(self):
        for property_obj in (self.draft, self.pending, self.rejected, self.hidden):
            with self.subTest(status=property_obj.status):
                url = reverse('smuhammad:property_detail', args=[property_obj.pk])
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_other_user_cannot_open_foreign_draft(self):
        self.client.login(username='other', password='pass-12345')
        url = reverse('smuhammad:property_detail', args=[self.draft.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_owner_opens_own_unpublished_detail(self):
        self.client.login(username='owner', password='pass-12345')
        for property_obj in (self.draft, self.pending, self.rejected, self.hidden):
            with self.subTest(status=property_obj.status):
                url = reverse('smuhammad:property_detail', args=[property_obj.pk])
                self.assertEqual(self.client.get(url).status_code, 200)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PropertyCreateEditDeleteTests(PropertyTestCase):
    """Создание, правка и удаление: только свой объект и только через форму."""

    def test_guest_is_redirected_to_login_on_create(self):
        response = self.client.get(reverse('smuhammad:property_create'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('firuz:login')))

    def test_owner_creates_property_as_draft(self):
        self.client.login(username='owner', password='pass-12345')
        response = self.client.post(
            reverse('smuhammad:property_create'), self.valid_form_data()
        )
        property_obj = Property.objects.get()
        self.assertRedirects(
            response,
            reverse('smuhammad:property_images', args=[property_obj.pk]),
        )
        self.assertEqual(property_obj.owner, self.owner)
        self.assertEqual(property_obj.status, PropertyStatus.DRAFT)
        self.assertEqual(property_obj.moderation_reason, '')

    def test_form_cannot_set_owner_status_or_moderation_reason(self):
        self.client.login(username='owner', password='pass-12345')
        tampered = self.valid_form_data(
            status=PropertyStatus.APPROVED,
            moderation_reason='сам одобрил',
            owner=self.other_user.pk,
        )
        self.client.post(reverse('smuhammad:property_create'), tampered)
        property_obj = Property.objects.get()
        self.assertEqual(property_obj.owner, self.owner)
        self.assertEqual(property_obj.status, PropertyStatus.DRAFT)
        self.assertEqual(property_obj.moderation_reason, '')

    def test_negative_and_zero_price_are_not_saved(self):
        self.client.login(username='owner', password='pass-12345')
        for price in ('0', '-100.50'):
            with self.subTest(price=price):
                response = self.client.post(
                    reverse('smuhammad:property_create'),
                    self.valid_form_data(price=price),
                )
                self.assertEqual(response.status_code, 200)
                self.assertFormError(
                    response.context['form'],
                    'price',
                    'Цена за сутки должна быть больше нуля.',
                )
        self.assertEqual(Property.objects.count(), 0)

    def test_guest_cannot_create_property(self):
        response = self.client.post(
            reverse('smuhammad:property_create'), self.valid_form_data()
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('firuz:login')))
        self.assertEqual(Property.objects.count(), 0)

    def test_other_user_cannot_edit_foreign_property(self):
        property_obj = self.create_property()
        self.client.login(username='other', password='pass-12345')
        edit_url = reverse('smuhammad:property_edit', args=[property_obj.pk])
        self.assertEqual(self.client.get(edit_url).status_code, 404)
        response = self.client.post(
            edit_url, self.valid_form_data(title='Чужая правка')
        )
        self.assertEqual(response.status_code, 404)
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.title, 'Сдам квартиру')

    def test_other_user_cannot_delete_foreign_property(self):
        property_obj = self.create_property()
        self.client.login(username='other', password='pass-12345')
        delete_url = reverse('smuhammad:property_delete', args=[property_obj.pk])
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Property.objects.filter(pk=property_obj.pk).exists())

    def test_get_on_delete_shows_confirmation_and_keeps_property(self):
        property_obj = self.create_property()
        self.client.login(username='owner', password='pass-12345')
        response = self.client.get(
            reverse('smuhammad:property_delete', args=[property_obj.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Property.objects.filter(pk=property_obj.pk).exists())

    def test_owner_deletes_own_property_with_post(self):
        property_obj = self.create_property()
        self.client.login(username='owner', password='pass-12345')
        response = self.client.post(
            reverse('smuhammad:property_delete', args=[property_obj.pk])
        )
        self.assertRedirects(response, reverse('smuhammad:my_properties'))
        self.assertFalse(Property.objects.filter(pk=property_obj.pk).exists())

    def test_editing_approved_property_goes_back_to_pending(self):
        property_obj = self.create_property(status=PropertyStatus.APPROVED)
        self.client.login(username='owner', password='pass-12345')
        response = self.client.post(
            reverse('smuhammad:property_edit', args=[property_obj.pk]),
            self.valid_form_data(price='400.00'),
        )
        self.assertEqual(response.status_code, 302)
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status, PropertyStatus.PENDING)
        self.assertEqual(property_obj.price, Decimal('400.00'))

    def test_owner_cannot_approve_property_through_edit_form(self):
        property_obj = self.create_property(status=PropertyStatus.PENDING)
        self.client.login(username='owner', password='pass-12345')
        response = self.client.post(
            reverse('smuhammad:property_edit', args=[property_obj.pk]),
            self.valid_form_data(status=PropertyStatus.APPROVED),
        )
        self.assertEqual(response.status_code, 302)
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status, PropertyStatus.PENDING)

    def test_there_is_no_approve_url_in_my_app(self):
        with self.assertRaises(NoReverseMatch):
            reverse('smuhammad:property_approve')


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PropertyStatusActionTests(PropertyTestCase):
    """Отправка на модерацию и скрытие: своё, только POST, только свои статусы."""

    def test_guest_submit_redirects_to_login(self):
        property_obj = self.create_property()
        response = self.client.post(
            reverse('smuhammad:property_submit', args=[property_obj.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('firuz:login')))
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status, PropertyStatus.DRAFT)

    def test_owner_submits_draft_to_moderation(self):
        property_obj = self.create_property()
        self.client.login(username='owner', password='pass-12345')
        response = self.client.post(
            reverse('smuhammad:property_submit', args=[property_obj.pk])
        )
        self.assertRedirects(
            response, reverse('smuhammad:property_detail', args=[property_obj.pk])
        )
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status, PropertyStatus.PENDING)

    def test_submit_is_post_only_and_get_keeps_status(self):
        property_obj = self.create_property()
        self.client.login(username='owner', password='pass-12345')
        response = self.client.get(
            reverse('smuhammad:property_submit', args=[property_obj.pk])
        )
        self.assertEqual(response.status_code, 405)
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status, PropertyStatus.DRAFT)

    def test_other_user_cannot_submit_foreign_property(self):
        property_obj = self.create_property()
        self.client.login(username='other', password='pass-12345')
        response = self.client.post(
            reverse('smuhammad:property_submit', args=[property_obj.pk])
        )
        self.assertEqual(response.status_code, 404)
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status, PropertyStatus.DRAFT)

    def test_pending_property_cannot_be_submitted_again(self):
        property_obj = self.create_property(status=PropertyStatus.PENDING)
        self.client.login(username='owner', password='pass-12345')
        self.client.post(reverse('smuhammad:property_submit', args=[property_obj.pk]))
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status, PropertyStatus.PENDING)

    def test_submit_clears_rejection_reason(self):
        property_obj = self.create_property(
            status=PropertyStatus.REJECTED, moderation_reason='Не хватает фотографий'
        )
        self.client.login(username='owner', password='pass-12345')
        self.client.post(reverse('smuhammad:property_submit', args=[property_obj.pk]))
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status, PropertyStatus.PENDING)
        self.assertEqual(property_obj.moderation_reason, '')

    def test_owner_hides_approved_property(self):
        property_obj = self.create_property(status=PropertyStatus.APPROVED)
        self.client.login(username='owner', password='pass-12345')
        response = self.client.post(
            reverse('smuhammad:property_hide', args=[property_obj.pk])
        )
        self.assertRedirects(
            response, reverse('smuhammad:property_detail', args=[property_obj.pk])
        )
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status, PropertyStatus.HIDDEN)
        # скрытое объявление пропадает из каталога для гостя
        catalog = self.client.get(reverse('smuhammad:property_list'))
        self.assertNotIn(property_obj, list(catalog.context['properties']))

    def test_hide_is_post_only_and_get_keeps_status(self):
        property_obj = self.create_property(status=PropertyStatus.APPROVED)
        self.client.login(username='owner', password='pass-12345')
        response = self.client.get(
            reverse('smuhammad:property_hide', args=[property_obj.pk])
        )
        self.assertEqual(response.status_code, 405)
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status, PropertyStatus.APPROVED)

    def test_other_user_cannot_hide_foreign_property(self):
        property_obj = self.create_property(status=PropertyStatus.APPROVED)
        self.client.login(username='other', password='pass-12345')
        response = self.client.post(
            reverse('smuhammad:property_hide', args=[property_obj.pk])
        )
        self.assertEqual(response.status_code, 404)
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status, PropertyStatus.APPROVED)

    def test_draft_cannot_be_hidden(self):
        property_obj = self.create_property(status=PropertyStatus.DRAFT)
        self.client.login(username='owner', password='pass-12345')
        self.client.post(reverse('smuhammad:property_hide', args=[property_obj.pk]))
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status, PropertyStatus.DRAFT)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class MyPropertiesTests(PropertyTestCase):
    """Мои объявления: все статусы своих записей, чужие не показываются."""

    def test_guest_is_redirected_to_login(self):
        response = self.client.get(reverse('smuhammad:my_properties'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('firuz:login')))

    def test_owner_sees_own_properties_in_all_statuses(self):
        own_draft = self.create_property(status=PropertyStatus.DRAFT, title='Мой черновик')
        own_approved = self.create_property(
            status=PropertyStatus.APPROVED, title='Мое опубликованное'
        )
        foreign = self.create_property(
            owner=self.other_user, status=PropertyStatus.APPROVED, title='Чужое'
        )
        self.client.login(username='owner', password='pass-12345')
        response = self.client.get(reverse('smuhammad:my_properties'))
        properties = list(response.context['properties'])
        self.assertIn(own_draft, properties)
        self.assertIn(own_approved, properties)
        self.assertNotIn(foreign, properties)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PropertyImageTests(PropertyTestCase):
    """Фотографии: чужими не управляются, файлы проверяются формой."""

    def setUp(self):
        self.property_obj = self.create_property(status=PropertyStatus.APPROVED)

    def add_images_url(self):
        return reverse('smuhammad:property_images_add', args=[self.property_obj.pk])

    def test_guest_is_redirected_to_login_on_images_page(self):
        response = self.client.get(
            reverse('smuhammad:property_images', args=[self.property_obj.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('firuz:login')))

    def test_other_user_cannot_open_or_upload_images(self):
        self.client.login(username='other', password='pass-12345')
        page = self.client.get(
            reverse('smuhammad:property_images', args=[self.property_obj.pk])
        )
        self.assertEqual(page.status_code, 404)
        response = self.client.post(
            self.add_images_url(), {'images': [make_image()]}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.property_obj.images.count(), 0)

    def test_owner_uploads_several_valid_images(self):
        self.client.login(username='owner', password='pass-12345')
        response = self.client.post(
            self.add_images_url(),
            {'images': [make_image('one.jpg', (10, 20, 30)), make_image('two.jpg', (90, 80, 70))]},
        )
        self.assertRedirects(
            response,
            reverse('smuhammad:property_images', args=[self.property_obj.pk]),
        )
        self.assertEqual(self.property_obj.images.count(), 2)

    def test_file_that_is_not_an_image_is_rejected(self):
        self.client.login(username='owner', password='pass-12345')
        fake = SimpleUploadedFile('not-a-photo.jpg', b'just text', content_type='image/jpeg')
        response = self.client.post(self.add_images_url(), {'images': [fake]})
        self.assertEqual(response.status_code, 302)
        messages_list = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertIn('Фотографии не загружены', messages_list[0])
        self.assertEqual(self.property_obj.images.count(), 0)

    def test_upload_without_files_is_rejected(self):
        self.client.login(username='owner', password='pass-12345')
        self.client.post(self.add_images_url(), {})
        self.assertEqual(self.property_obj.images.count(), 0)

    def test_upload_over_limit_is_rejected(self):
        for index in range(MAX_IMAGES_PER_PROPERTY):
            PropertyImage.objects.create(
                property=self.property_obj, image=make_image(f'old-{index}.jpg')
            )
        self.client.login(username='owner', password='pass-12345')
        self.client.post(self.add_images_url(), {'images': [make_image('extra.jpg')]})
        self.assertEqual(self.property_obj.images.count(), MAX_IMAGES_PER_PROPERTY)

    def test_other_user_cannot_delete_foreign_image(self):
        image = PropertyImage.objects.create(
            property=self.property_obj, image=make_image()
        )
        self.client.login(username='other', password='pass-12345')
        response = self.client.post(
            reverse('smuhammad:property_image_delete', args=[image.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(PropertyImage.objects.filter(pk=image.pk).exists())

    def test_owner_deletes_own_image_with_post(self):
        image = PropertyImage.objects.create(
            property=self.property_obj, image=make_image()
        )
        self.client.login(username='owner', password='pass-12345')
        response = self.client.post(
            reverse('smuhammad:property_image_delete', args=[image.pk])
        )
        self.assertRedirects(
            response,
            reverse('smuhammad:property_images', args=[self.property_obj.pk]),
        )
        self.assertFalse(PropertyImage.objects.filter(pk=image.pk).exists())

    def test_get_on_image_delete_keeps_image(self):
        image = PropertyImage.objects.create(
            property=self.property_obj, image=make_image()
        )
        self.client.login(username='owner', password='pass-12345')
        response = self.client.get(
            reverse('smuhammad:property_image_delete', args=[image.pk])
        )
        self.assertEqual(response.status_code, 405)
        self.assertTrue(PropertyImage.objects.filter(pk=image.pk).exists())
