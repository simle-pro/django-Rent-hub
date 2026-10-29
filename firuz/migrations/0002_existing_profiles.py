from django.conf import settings
from django.db import migrations


def create_existing_profiles(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(app_label, model_name)
    Profile = apps.get_model('firuz', 'Profile')
    Group = apps.get_model('auth', 'Group')
    database = schema_editor.connection.alias
    tenant, _ = Group.objects.using(database).get_or_create(name='tenant')
    for user in User.objects.using(database).all().iterator():
        _, created = Profile.objects.using(database).get_or_create(user_id=user.pk)
        if created:
            user.groups.add(tenant)


class Migration(migrations.Migration):
    dependencies = [('firuz', '0001_initial')]
    operations = [migrations.RunPython(create_existing_profiles, migrations.RunPython.noop)]
