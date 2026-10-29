import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from smuhammad.models import Amenity, Location, Property, PropertyCategory

from .models import Booking, Favorite


class SimpleBaseTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user('owner1', password='RentHub-Test-9!')
        self.owner.profile.role = 'owner'
        self.owner.profile.save()
        self.tenant = user_model.objects.create_user('tenant1', password='RentHub-Test-9!')
        self.other = user_model.objects.create_user('tenant2', password='RentHub-Test-9!')
        self.category = PropertyCategory.objects.create(name='Квартира')
        self.location = Location.objects.create(city='Душанбе', address='Рудаки 1')
        self.wifi = Amenity.objects.create(name='Wi-Fi')
        self.parking = Amenity.objects.create(name='Парковка')
        self.property = self.make_property('Квартира в центре', status='approved')
        self.property.amenities.set([self.wifi, self.parking])

    def make_property(self, title, status='approved', owner=None, price=Decimal('100.00')):
        return Property.objects.create(
            owner=owner or self.owner,
            title=title,
            description='Уютное жильё',
            price=price,
            category=self.category,
            location=self.location,
            status=status,
        )

    def days(self, offset):
        return timezone.localdate() + datetime.timedelta(days=offset)

    def make_booking(self, user, start, end, status=Booking.STATUS_PENDING, property_obj=None):
        return Booking.objects.create(
            user=user,
            property=property_obj or self.property,
            start_date=start,
            end_date=end,
            status=status,
        )


class SearchTests(SimpleBaseTestCase):
    def test_search_shows_only_approved(self):
        self.make_property('Черновик', status='draft')
        self.make_property('На модерации', status='pending')
        self.make_property('Скрытый', status='hidden')
        response = self.client.get(reverse('simple:search'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Квартира в центре')
        self.assertNotContains(response, 'Черновик')
        self.assertNotContains(response, 'На модерации')
        self.assertNotContains(response, 'Скрытый')

    def test_search_by_title_and_location(self):
        response = self.client.get(reverse('simple:search'), {'q': 'центре'})
        self.assertContains(response, 'Квартира в центре')
        response = self.client.get(reverse('simple:search'), {'q': 'Душанбе'})
        self.assertContains(response, 'Квартира в центре')
        response = self.client.get(reverse('simple:search'), {'q': 'нет такого'})
        self.assertNotContains(response, 'Квартира в центре')

    def test_invalid_filters_do_not_give_500(self):
        response = self.client.get(reverse('simple:search'), {
            'q': '', 'min_price': 'abc', 'max_price': 'xyz', 'category': 'zzz',
            'amenities': ['junk', ''], 'sort': 'hack', 'page': 'abc',
        })
        self.assertEqual(response.status_code, 200)

    def test_price_category_and_amenity_filters(self):
        cheap = self.make_property('Дешёвый', price=Decimal('50.00'))
        cheap.amenities.set([self.wifi])
        response = self.client.get(reverse('simple:search'), {'min_price': '80'})
        self.assertContains(response, 'Квартира в центре')
        self.assertNotContains(response, 'Дешёвый')
        response = self.client.get(reverse('simple:search'), {'max_price': '60'})
        self.assertNotContains(response, 'Квартира в центре')
        self.assertContains(response, 'Дешёвый')
        response = self.client.get(reverse('simple:search'), {'category': self.category.pk})
        self.assertContains(response, 'Квартира в центре')
        response = self.client.get(reverse('simple:search'), {'category': 999999})
        self.assertNotContains(response, 'Квартира в центре')

    def test_amenities_require_all_selected(self):
        partial = self.make_property('Только Wi-Fi')
        partial.amenities.set([self.wifi])
        response = self.client.get(reverse('simple:search'), {'amenities': [str(self.wifi.pk)]})
        self.assertContains(response, 'Квартира в центре')
        self.assertContains(response, 'Только Wi-Fi')
        response = self.client.get(reverse('simple:search'), {
            'amenities': [str(self.wifi.pk), str(self.parking.pk)],
        })
        self.assertContains(response, 'Квартира в центре')
        self.assertNotContains(response, 'Только Wi-Fi')

    def test_sorting_whitelist(self):
        self.make_property('Дорогой', price=Decimal('300.00'))
        response = self.client.get(reverse('simple:search'), {'sort': 'price_asc'})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Дешёвый' if 'Дешёвый' in content else 'Квартира в центре', content)
        self.assertLess(content.index('Квартира в центре'), content.index('Дорогой'))
        response = self.client.get(reverse('simple:search'), {'sort': 'price_desc'})
        self.assertLess(response.content.decode().index('Дорогой'), response.content.decode().index('Квартира в центре'))
        response = self.client.get(reverse('simple:search'), {'sort': 'newest'})
        self.assertEqual(response.status_code, 200)

    def test_no_results_duplicates(self):
        response = self.client.get(reverse('simple:search'), {'amenities': [str(self.wifi.pk)]})
        self.assertEqual(response.content.decode().count('Квартира в центре'), 1)

    def test_pagination_keeps_filters(self):
        for index in range(12):
            self.make_property(f'Объект {index}')
        response = self.client.get(reverse('simple:search'), {'q': 'Объект', 'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'page=1')


class FavoriteTests(SimpleBaseTestCase):
    def test_toggle_requires_login(self):
        response = self.client.post(reverse('simple:favorite_toggle', args=[self.property.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('firuz:login'), response.url)
        self.assertFalse(Favorite.objects.exists())

    def test_toggle_requires_post_with_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.tenant)
        url = reverse('simple:favorite_toggle', args=[self.property.pk])
        self.assertEqual(client.get(url).status_code, 405)
        self.assertEqual(client.post(url).status_code, 403)
        self.assertFalse(Favorite.objects.exists())

    def test_toggle_add_and_remove_once(self):
        self.client.force_login(self.tenant)
        url = reverse('simple:favorite_toggle', args=[self.property.pk])
        self.client.post(url)
        self.assertEqual(Favorite.objects.filter(user=self.tenant, property=self.property).count(), 1)
        self.client.post(url)
        self.assertFalse(Favorite.objects.filter(user=self.tenant, property=self.property).exists())

    def test_favorites_are_not_shared_between_users(self):
        Favorite.objects.create(user=self.tenant, property=self.property)
        self.client.force_login(self.other)
        response = self.client.get(reverse('simple:favorite_list'))
        self.assertNotContains(response, 'Квартира в центре')
        self.client.force_login(self.tenant)
        response = self.client.get(reverse('simple:favorite_list'))
        self.assertContains(response, 'Квартира в центре')

    def test_cannot_favorite_hidden_property(self):
        hidden = self.make_property('Скрытый', status='hidden')
        self.client.force_login(self.tenant)
        response = self.client.post(reverse('simple:favorite_toggle', args=[hidden.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Favorite.objects.filter(property=hidden).exists())


class BookingCreateTests(SimpleBaseTestCase):
    def create_booking(self, property_obj=None, **extra):
        data = {
            'start_date': self.days(3).isoformat(),
            'end_date': self.days(6).isoformat(),
        }
        data.update(extra)
        property_obj = property_obj or self.property
        return self.client.post(reverse('simple:booking_create', args=[property_obj.pk]), data)

    def test_requires_login(self):
        response = self.create_booking()
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('firuz:login'), response.url)
        self.assertFalse(Booking.objects.exists())

    def test_only_tenant_can_create(self):
        self.owner.profile.role = 'owner'
        self.owner.profile.save()
        self.client.force_login(self.owner)
        response = self.create_booking()
        self.assertRedirects(response, reverse('firuz:profile'))
        self.assertFalse(Booking.objects.exists())

    def test_cannot_book_own_property(self):
        own = self.make_property('Своё', owner=self.tenant)
        self.client.force_login(self.tenant)
        response = self.create_booking(property_obj=own)
        self.assertRedirects(response, reverse('simple:search'))
        self.assertFalse(Booking.objects.filter(property=own).exists())

    def test_cannot_book_unapproved_property(self):
        draft = self.make_property('Черновик', status='draft')
        self.client.force_login(self.tenant)
        response = self.create_booking(property_obj=draft)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Booking.objects.filter(property=draft).exists())

    def test_invalid_dates_are_rejected(self):
        self.client.force_login(self.tenant)
        response = self.create_booking(start_date=self.days(6).isoformat(), end_date=self.days(3).isoformat())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Booking.objects.exists())
        response = self.create_booking(start_date=self.days(1).isoformat(), end_date=self.days(1).isoformat())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Booking.objects.exists())

    def test_past_start_is_rejected(self):
        self.client.force_login(self.tenant)
        response = self.create_booking(
            start_date=self.days(-3).isoformat(), end_date=self.days(3).isoformat(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Booking.objects.exists())

    def test_overlap_with_approved_is_rejected_adjacent_allowed(self):
        self.make_booking(self.other, self.days(10), self.days(12), status=Booking.STATUS_APPROVED)
        self.client.force_login(self.tenant)
        response = self.create_booking(start_date=self.days(11).isoformat(), end_date=self.days(13).isoformat())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Booking.objects.filter(user=self.tenant).exists())
        response = self.create_booking(start_date=self.days(12).isoformat(), end_date=self.days(14).isoformat())
        self.assertEqual(Booking.objects.filter(user=self.tenant).count(), 1)

    def test_form_cannot_accept_user_or_status(self):
        self.client.force_login(self.tenant)
        self.create_booking(status='approved', user=self.owner.pk)
        booking = Booking.objects.get()
        self.assertEqual(booking.user, self.tenant)
        self.assertEqual(booking.status, Booking.STATUS_PENDING)


class BookingPermissionTests(SimpleBaseTestCase):
    def test_detail_hidden_from_stranger(self):
        booking = self.make_booking(self.tenant, self.days(3), self.days(5))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('simple:booking_detail', args=[booking.pk])).status_code, 404)
        self.client.force_login(self.tenant)
        self.assertEqual(self.client.get(reverse('simple:booking_detail', args=[booking.pk])).status_code, 200)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('simple:booking_detail', args=[booking.pk])).status_code, 200)

    def test_received_list_shows_only_own_properties(self):
        booking = self.make_booking(self.tenant, self.days(3), self.days(5))
        other_owner = get_user_model().objects.create_user('owner2', password='RentHub-Test-9!')
        other_owner.profile.role = 'owner'
        other_owner.profile.save()
        foreign = self.make_property('Чужое', owner=other_owner)
        self.make_booking(self.other, self.days(3), self.days(5), property_obj=foreign)
        self.client.force_login(self.owner)
        response = self.client.get(reverse('simple:received_bookings'))
        self.assertContains(response, 'Квартира в центре')
        self.assertNotContains(response, 'Чужое')
        self.assertEqual(response.context['bookings'].count(), 1)
        self.assertEqual(response.context['bookings'].first(), booking)

    def test_cancel_only_author(self):
        booking = self.make_booking(self.tenant, self.days(3), self.days(5))
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.post(reverse('simple:booking_cancel', args=[booking.pk])).status_code, 404,
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_PENDING)
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.post(reverse('simple:booking_cancel', args=[booking.pk])).status_code, 404,
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_PENDING)

    def test_cancel_only_pending_or_approved(self):
        for status in (Booking.STATUS_REJECTED, Booking.STATUS_CANCELLED):
            booking = self.make_booking(self.tenant, self.days(3), self.days(5), status=status)
            self.client.force_login(self.tenant)
            self.client.post(reverse('simple:booking_cancel', args=[booking.pk]))
            booking.refresh_from_db()
            self.assertEqual(booking.status, status)

    def test_get_cancel_does_not_change_state(self):
        booking = self.make_booking(self.tenant, self.days(3), self.days(5))
        self.client.force_login(self.tenant)
        response = self.client.get(reverse('simple:booking_cancel', args=[booking.pk]))
        self.assertEqual(response.status_code, 405)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_PENDING)

    def test_approve_and_reject_only_property_owner(self):
        booking = self.make_booking(self.tenant, self.days(3), self.days(5))
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.post(reverse('simple:booking_approve', args=[booking.pk])).status_code, 404,
        )
        self.assertEqual(
            self.client.post(reverse('simple:booking_reject', args=[booking.pk])).status_code, 404,
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_PENDING)

    def test_get_approve_and_reject_do_not_change_state(self):
        booking = self.make_booking(self.tenant, self.days(3), self.days(5))
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('simple:booking_approve', args=[booking.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse('simple:booking_reject', args=[booking.pk])).status_code, 405)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_PENDING)

    def test_approve_success_and_second_transition_blocked(self):
        booking = self.make_booking(self.tenant, self.days(3), self.days(5))
        self.client.force_login(self.owner)
        response = self.client.post(reverse('simple:booking_approve', args=[booking.pk]))
        self.assertRedirects(response, reverse('simple:booking_detail', args=[booking.pk]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_APPROVED)
        response = self.client.post(reverse('simple:booking_approve', args=[booking.pk]))
        self.assertRedirects(response, reverse('simple:booking_detail', args=[booking.pk]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_APPROVED)
        response = self.client.post(reverse('simple:booking_reject', args=[booking.pk]))
        self.assertRedirects(response, reverse('simple:booking_detail', args=[booking.pk]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_APPROVED)

    def test_reject_only_pending(self):
        booking = self.make_booking(self.tenant, self.days(3), self.days(5), status=Booking.STATUS_APPROVED)
        self.client.force_login(self.owner)
        self.client.post(reverse('simple:booking_reject', args=[booking.pk]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_APPROVED)

    def test_approve_rechecks_overlap_between_two_pending(self):
        first = self.make_booking(self.tenant, self.days(10), self.days(12))
        second = self.make_booking(self.other, self.days(11), self.days(13))
        self.client.force_login(self.owner)
        self.client.post(reverse('simple:booking_approve', args=[first.pk]))
        self.client.post(reverse('simple:booking_approve', args=[second.pk]))
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, Booking.STATUS_APPROVED)
        self.assertEqual(second.status, Booking.STATUS_PENDING)

    def test_adjacent_bookings_can_both_be_approved(self):
        first = self.make_booking(self.tenant, self.days(10), self.days(12))
        second = self.make_booking(self.other, self.days(12), self.days(14))
        self.client.force_login(self.owner)
        self.client.post(reverse('simple:booking_approve', args=[first.pk]))
        self.client.post(reverse('simple:booking_approve', args=[second.pk]))
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, Booking.STATUS_APPROVED)
        self.assertEqual(second.status, Booking.STATUS_APPROVED)
