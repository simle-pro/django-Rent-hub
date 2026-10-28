import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse


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
