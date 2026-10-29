from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, raw=False, using='default', **kwargs):
    if created and not raw:
        Profile.objects.using(using).get_or_create(user=instance)


@receiver(post_save, sender=Profile)
def assign_role(sender, instance, raw=False, using='default', **kwargs):
    if raw:
        return
    group, _ = Group.objects.using(using).get_or_create(name=instance.role)
    previous = Group.objects.using(using).filter(name__in=['tenant', 'owner', 'moderator']).exclude(pk=group.pk)
    instance.user.groups.remove(*previous)
    instance.user.groups.add(group)


@receiver(post_migrate)
def create_role_groups(sender, using, **kwargs):
    if sender.name != 'firuz':
        return
    for role, _ in Profile.ROLE_CHOICES:
        Group.objects.using(using).get_or_create(name=role)
    permission = Permission.objects.using(using).get(
        content_type__app_label='firuz', content_type__model='profile', codename='moderate_property',
    )
    Group.objects.using(using).get(name='moderator').permissions.add(permission)
