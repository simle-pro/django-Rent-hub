import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from simple.models import Booking
from smuhammad.models import Property, PropertyCategory, Location

from .models import Review, PropertyReport


@override_settings(ROOT_URLCONF='firuz.dev_urls', MAILERS={
    'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'},
})
class AccountTests(TestCase):
    def register(self, **changes):
        data = {
            'username': 'firuz', 'email': 'firuz@example.com', 'role': 'owner',
            'password1': 'RentHub-Test-927!', 'password2': 'RentHub-Test-927!',
        }
        data.update(changes)
        return self.client.post(reverse('firuz:register'), data)

    def test_registration_activation_and_login(self):
        self.assertRedirects(self.register(), reverse('firuz:login'))
        user = get_user_model().objects.get(username='firuz')
        self.assertFalse(user.is_active)
        self.assertEqual(user.profile.role, 'owner')
        self.assertTrue(user.groups.filter(name='owner').exists())
        self.assertFalse(self.client.login(username='firuz', password='RentHub-Test-927!'))
        link = re.search(r'http://testserver\S+', mail.outbox[0].body).group()
        self.assertEqual(self.client.get(link).status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertRedirects(self.client.post(link), reverse('firuz:login'))
        self.assertEqual(self.client.post(link).status_code, 400)
        response = self.client.post(reverse('firuz:login'), {
            'username': 'firuz', 'password': 'RentHub-Test-927!', 'next': 'https://example.com/',
        })
        self.assertRedirects(response, reverse('firuz:profile'))

    def test_registration_cannot_grant_moderator_role(self):
        self.assertEqual(self.register(role='moderator').status_code, 200)
        self.assertFalse(get_user_model().objects.exists())

    def test_duplicate_email_is_rejected_case_insensitively(self):
        get_user_model().objects.create_user('existing', email='FIRUZ@example.com')
        self.register()
        self.assertFalse(get_user_model().objects.filter(username='firuz').exists())

    def test_profile_edits_only_current_user_and_cannot_change_role(self):
        user = get_user_model().objects.create_user('tenant')
        other = get_user_model().objects.create_user('other')
        self.client.force_login(user)
        response = self.client.post(reverse('firuz:profile_edit'), {
            'first_name': 'Фируз', 'last_name': '', 'phone': '+992123456789',
            'bio': 'Арендатор', 'role': 'moderator', 'user': other.pk, 'is_staff': 'on',
        })
        self.assertRedirects(response, reverse('firuz:profile'))
        user.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(user.first_name, 'Фируз')
        self.assertEqual(user.profile.role, 'tenant')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.has_perm('firuz.moderate_property'))
        self.assertEqual(other.first_name, '')

    def test_moderator_group_permission_and_role_change(self):
        user = get_user_model().objects.create_user('moderator')
        profile = user.profile
        profile.role = 'moderator'
        profile.save()
        user = get_user_model().objects.get(pk=user.pk)
        self.assertTrue(user.has_perm('firuz.moderate_property'))
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse('firuz:profile')), 'Кабинет модератора')
        profile.role = 'owner'
        profile.save()
        user = get_user_model().objects.get(pk=user.pk)
        self.assertFalse(user.has_perm('firuz.moderate_property'))
        self.assertFalse(user.groups.filter(name='moderator').exists())

    def test_logout_requires_post_and_csrf(self):
        user = get_user_model().objects.create_user('tenant')
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        self.assertEqual(client.get(reverse('firuz:logout')).status_code, 405)
        self.assertEqual(client.post(reverse('firuz:logout')).status_code, 403)
        client.get(reverse('firuz:profile'))
        response = client.post(reverse('firuz:logout'), {'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('_auth_user_id', client.session)

    def test_public_profile_exposes_only_active_owners(self):
        owner = get_user_model().objects.create_user('owner', email='private@example.com')
        owner.profile.role = 'owner'
        owner.profile.phone = 'private-phone'
        owner.profile.save()
        response = self.client.get(reverse('firuz:public_profile', args=[owner.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'private@example.com')
        self.assertNotContains(response, 'private-phone')
        tenant = get_user_model().objects.create_user('tenant')
        self.assertEqual(self.client.get(reverse('firuz:public_profile', args=[tenant.pk])).status_code, 404)

    def test_anonymous_profile_redirects_to_own_login(self):
        response = self.client.get(reverse('firuz:profile'))
        self.assertRedirects(response, reverse('firuz:login') + '?next=' + reverse('firuz:profile'))


class ReviewModerationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user('owner')
        cls.owner.profile.role = 'owner'
        cls.owner.profile.save()
        cls.tenant = User.objects.create_user('tenant')
        cls.other = User.objects.create_user('other')
        cls.moderator = User.objects.create_user('moderator')
        cls.moderator.profile.role = 'moderator'
        cls.moderator.profile.save()
        cls.category = PropertyCategory.objects.create(name='Квартира')
        cls.location = Location.objects.create(city='Душанбе', address='Рудаки 1')
        cls.property = Property.objects.create(
            owner=cls.owner, title='Квартира у парка', description='Две комнаты',
            price='150.00', category=cls.category, location=cls.location, status='approved',
        )

    def post_as(self, user, name, pk, data=None):
        self.client.force_login(user)
        return self.client.post(reverse('firuz:' + name, args=[pk]), data or {})

    def report(self):
        return PropertyReport.objects.create(user=self.tenant, property=self.property, reason='incorrect', text='Неверный адрес')

    def test_review_uses_current_user_and_fixed_property(self):
        response = self.post_as(self.tenant, 'review_create', self.property.pk, {
            'rating': 5, 'text': '<script>bad()</script>', 'user': self.owner.pk,
            'property': 999, 'created_at': '2000-01-01',
        })
        self.assertRedirects(response, reverse('firuz:property_reviews', args=[self.property.pk]))
        review = Review.objects.get()
        self.assertEqual(review.user, self.tenant)
        self.assertEqual(review.property, self.property)
        response = self.client.get(reverse('firuz:property_reviews', args=[self.property.pk]))
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>bad()</script>')

    def test_duplicate_and_invalid_reviews_do_not_save(self):
        for rating, text in [(0, 'Текст'), (6, 'Текст'), (3, '   '), (4, 'x' * 2001)]:
            with self.subTest(rating=rating, length=len(text)):
                response = self.post_as(self.tenant, 'review_create', self.property.pk, {'rating': rating, 'text': text})
                self.assertEqual(response.status_code, 400)
        self.assertFalse(Review.objects.exists())
        self.post_as(self.tenant, 'review_create', self.property.pk, {'rating': 4, 'text': 'Хорошо'})
        response = self.post_as(self.tenant, 'review_create', self.property.pk, {'rating': 5, 'text': 'Повтор'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Review.objects.count(), 1)

    def test_review_database_constraints(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(user=self.tenant, property=self.property, rating=6, text='Текст')
        Review.objects.create(user=self.tenant, property=self.property, rating=3, text='Текст')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(user=self.tenant, property=self.property, rating=4, text='Повтор')

    def test_owner_and_moderator_cannot_review(self):
        for user in [self.owner, self.moderator]:
            self.assertEqual(self.post_as(user, 'review_create', self.property.pk, {'rating': 5, 'text': 'Текст'}).status_code, 403)
        self.owner.profile.role = 'tenant'
        self.owner.profile.save()
        self.assertEqual(self.post_as(self.owner, 'review_create', self.property.pk, {'rating': 5, 'text': 'Свой объект'}).status_code, 403)

    def test_hidden_properties_and_reviews_not_public(self):
        self.property.status = 'hidden'
        self.property.save()
        self.assertEqual(self.client.get(reverse('firuz:property_reviews', args=[self.property.pk])).status_code, 404)
        self.assertEqual(self.post_as(self.tenant, 'review_create', self.property.pk, {'rating': 4, 'text': 'Текст'}).status_code, 404)
        self.assertEqual(self.post_as(self.tenant, 'report_create', self.property.pk, {'reason': 'other', 'text': 'Текст'}).status_code, 404)

    def test_only_author_can_delete_review_even_when_hidden(self):
        review = Review.objects.create(user=self.tenant, property=self.property, rating=4, text='Текст')
        self.assertEqual(self.post_as(self.other, 'review_delete', review.pk).status_code, 404)
        self.assertTrue(Review.objects.filter(pk=review.pk).exists())
        self.property.status = 'hidden'
        self.property.save()
        response = self.post_as(self.tenant, 'review_delete', review.pk)
        self.assertRedirects(response, reverse('firuz:profile'))
        self.assertFalse(Review.objects.exists())

    def test_public_owner_page_filters_properties_and_paginates(self):
        Property.objects.create(
            owner=self.owner, title='Секретный черновик', description='Текст', price='10',
            category=self.category, location=self.location, status='draft',
        )
        for index in range(12):
            Property.objects.create(
                owner=self.owner, title=f'Квартира {index}', description='Текст', price='10',
                category=self.category, location=self.location, status='approved',
            )
        response = self.client.get(reverse('firuz:public_profile', args=[self.owner.pk]))
        self.assertNotContains(response, 'Секретный черновик')
        self.assertEqual(len(response.context['page_obj']), 12)
        self.assertContains(response, '?page=2')

    def test_review_directory_pagination(self):
        response = self.client.get(reverse('firuz:review_list'))
        self.assertContains(response, 'Квартира у парка')
        self.assertContains(response, reverse('firuz:property_reviews', args=[self.property.pk]))
        for index in range(11):
            user = get_user_model().objects.create_user(f'reviewer{index}')
            Review.objects.create(user=user, property=self.property, rating=4, text='Текст')
        response = self.client.get(reverse('firuz:property_reviews', args=[self.property.pk]))
        self.assertEqual(len(response.context['page_obj']), 10)
        self.assertEqual(response.context['average_rating'], 4)

    def test_moderation_requires_permission_not_staff_flag(self):
        self.tenant.is_staff = True
        self.tenant.save()
        report = self.report()
        for user in [self.tenant, self.owner]:
            self.client.force_login(user)
            for name in ['pending_properties', 'property_reports']:
                self.assertEqual(self.client.get(reverse('firuz:' + name)).status_code, 403)
            for name, pk in [('property_approve', self.property.pk), ('property_reject', self.property.pk), ('report_resolve', report.pk)]:
                self.assertEqual(self.client.post(reverse('firuz:' + name, args=[pk])).status_code, 403)

    def test_approve_only_pending_and_clear_reason(self):
        self.assertEqual(self.post_as(self.moderator, 'property_approve', self.property.pk).status_code, 404)
        self.property.status = 'pending'
        self.property.moderation_reason = 'Старое замечание'
        self.property.save()
        self.assertRedirects(self.post_as(self.moderator, 'property_approve', self.property.pk), reverse('firuz:pending_properties'))
        self.property.refresh_from_db()
        self.assertEqual(self.property.status, 'approved')
        self.assertEqual(self.property.moderation_reason, '')
        self.assertEqual(self.post_as(self.moderator, 'property_approve', self.property.pk).status_code, 404)

    def test_reject_requires_reason_and_owner_can_resubmit(self):
        self.property.status = 'pending'
        self.property.save()
        self.assertEqual(self.post_as(self.moderator, 'property_reject', self.property.pk, {'reason': '   '}).status_code, 400)
        self.property.refresh_from_db()
        self.assertEqual(self.property.status, 'pending')
        response = self.post_as(self.moderator, 'property_reject', self.property.pk, {'reason': 'Исправьте адрес'})
        self.assertEqual(response.status_code, 302)
        self.property.refresh_from_db()
        self.assertEqual(self.property.status, 'rejected')
        self.assertEqual(self.property.moderation_reason, 'Исправьте адрес')
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.property.get_absolute_url()), 'Исправьте адрес')
        self.client.post(reverse('smuhammad:property_submit', args=[self.property.pk]))
        self.property.refresh_from_db()
        self.assertEqual(self.property.status, 'pending')
        self.assertEqual(self.property.moderation_reason, '')

    def test_moderator_cannot_moderate_own_property(self):
        self.property.owner = self.moderator
        self.property.status = 'pending'
        self.property.save()
        for name in ['property_approve', 'property_reject']:
            self.assertEqual(self.post_as(self.moderator, name, self.property.pk, {'reason': 'Текст'}).status_code, 403)
        response = self.client.get(reverse('firuz:pending_properties'))
        self.assertNotContains(response, 'Квартира у парка')

    def test_reports_validate_fields_and_prevent_pending_duplicate(self):
        self.client.force_login(self.tenant)
        url = reverse('firuz:report_create', args=[self.property.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {'reason': 'fake', 'text': '   '})
        self.assertFalse(PropertyReport.objects.exists())
        self.assertEqual(self.client.post(url, {'reason': 'incorrect', 'text': 'Неверный адрес', 'user': self.owner.pk, 'status': 'resolved'}).status_code, 302)
        report = PropertyReport.objects.get()
        self.assertEqual(report.user, self.tenant)
        self.assertEqual(report.status, 'pending')
        self.assertContains(self.client.post(url, {'reason': 'fraud', 'text': 'Повтор'}), 'уже рассматривается')
        self.assertEqual(PropertyReport.objects.count(), 1)
        self.assertEqual(self.post_as(self.owner, 'report_create', self.property.pk, {'reason': 'other', 'text': 'Свой объект'}).status_code, 403)

    def test_report_resolution_keeps_audit_and_can_hide_property(self):
        report = self.report()
        response = self.post_as(self.moderator, 'report_resolve', report.pk, {'resolution': 'Адрес неверный', 'hide_property': 'on'})
        self.assertRedirects(response, reverse('firuz:property_reports'))
        report.refresh_from_db()
        self.property.refresh_from_db()
        self.assertEqual(report.status, 'resolved')
        self.assertEqual(report.resolved_by, self.moderator)
        self.assertIsNotNone(report.resolved_at)
        self.assertEqual(self.property.status, 'hidden')
        self.assertEqual(self.post_as(self.moderator, 'report_resolve', report.pk, {'resolution': 'Заменить'}).status_code, 404)
        self.client.force_login(self.tenant)
        self.assertContains(self.client.get(reverse('firuz:profile')), 'Адрес неверный')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse('firuz:profile')), 'Адрес неверный')

    def test_resolution_requires_text_and_does_not_republish(self):
        report = self.report()
        self.assertEqual(self.post_as(self.moderator, 'report_resolve', report.pk, {'resolution': '   '}).status_code, 400)
        self.property.status = 'pending'
        self.property.save()
        self.assertEqual(self.post_as(self.moderator, 'report_resolve', report.pk, {'resolution': 'Проверено', 'hide_property': 'on'}).status_code, 400)
        report.refresh_from_db()
        self.assertEqual(report.status, 'pending')
        self.assertEqual(self.post_as(self.moderator, 'report_resolve', report.pk, {'resolution': 'Недостаточно сведений'}).status_code, 302)
        self.property.refresh_from_db()
        self.assertEqual(self.property.status, 'pending')

    def test_moderator_cannot_resolve_own_property_report(self):
        report = self.report()
        self.property.owner = self.moderator
        self.property.save()
        self.assertEqual(self.post_as(self.moderator, 'report_resolve', report.pk, {'resolution': 'Закрыть'}).status_code, 403)

    def test_actions_require_post_and_csrf(self):
        review = Review.objects.create(user=self.tenant, property=self.property, rating=4, text='Текст')
        report = self.report()
        for user, actions in [
            (self.tenant, [('review_create', self.property.pk), ('review_delete', review.pk)]),
            (self.moderator, [('property_approve', self.property.pk), ('property_reject', self.property.pk), ('report_resolve', report.pk)]),
        ]:
            client = Client(enforce_csrf_checks=True)
            client.force_login(user)
            for name, pk in actions:
                url = reverse('firuz:' + name, args=[pk])
                self.assertEqual(client.get(url).status_code, 405)
                self.assertEqual(client.post(url).status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.tenant)
        self.assertEqual(client.post(reverse('firuz:report_create', args=[self.property.pk]), {'reason': 'other', 'text': 'Текст'}).status_code, 403)

    def test_complete_team_scenario(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('smuhammad:property_create'), {
            'title': 'Новое объявление', 'description': 'Уютная квартира', 'price': '100',
            'category': self.category.pk, 'location': self.location.pk,
        })
        self.assertEqual(response.status_code, 302)
        property_obj = Property.objects.get(title='Новое объявление')
        self.client.post(reverse('smuhammad:property_submit', args=[property_obj.pk]))
        self.post_as(self.moderator, 'property_approve', property_obj.pk)
        self.client.force_login(self.tenant)
        self.assertContains(self.client.get(reverse('simple:search'), {'q': property_obj.title}), property_obj.title)
        self.client.post(reverse('simple:favorite_toggle', args=[property_obj.pk]))
        self.assertTrue(self.tenant.favorites.filter(property=property_obj).exists())
        response = self.client.post(reverse('simple:booking_create', args=[property_obj.pk]), {
            'start_date': timezone.localdate() + timedelta(days=1),
            'end_date': timezone.localdate() + timedelta(days=3),
        })
        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get(property=property_obj)
        self.client.force_login(self.owner)
        self.client.post(reverse('simple:booking_approve', args=[booking.pk]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'approved')
        self.assertEqual(self.post_as(self.tenant, 'review_create', property_obj.pk, {'rating': 5, 'text': 'Хорошая квартира'}).status_code, 302)
        self.post_as(self.tenant, 'report_create', property_obj.pk, {'reason': 'incorrect', 'text': 'Неверный адрес'})
        report = PropertyReport.objects.get(property=property_obj)
        self.post_as(self.moderator, 'report_resolve', report.pk, {'resolution': 'Проверено, объявление скрыто', 'hide_property': 'on'})
        self.assertNotContains(self.client.get(reverse('simple:search'), {'q': property_obj.title}), 'href="' + property_obj.get_absolute_url() + '"')
