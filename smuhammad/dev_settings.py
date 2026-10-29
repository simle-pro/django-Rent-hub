"""Изолированные настройки для разработки и проверки приложения smuhammad.

Команды из корня проекта (аналог simple/dev_settings.py и firuz/dev_settings.py):

    python manage.py migrate --settings=smuhammad.dev_settings
    python manage.py runserver --settings=smuhammad.dev_settings
    python manage.py test smuhammad --settings=smuhammad.dev_settings

Общий server/settings.py не редактируется, база своя: smuhammad/db.sqlite3.
ROOT_URLCONF указывает на smuhammad.dev_urls, потому что общий server/urls.py
сейчас не загружается: simple/views.py делает `from firuz.models import
Amenity, Property`, а у firuz есть только Profile.
"""
from server.settings import *  # noqa: F401,F403

ROOT_URLCONF = 'smuhammad.dev_urls'

# Изолированная проверка: приложение simple сейчас ломает общий запуск,
# simple/models.py объявляет ForeignKey('firuz.Property'), а модели Property
# у firuz нет (она моя — smuhammad.Property). Чужую папку не правлю, поэтому
# simple в своей dev-конфигурации не подключаю. После согласования контракта
# и правки у simple строку ниже нужно удалить.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'simple']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'smuhammad' / 'db.sqlite3',
    },
}

# Фрагмент для ответственного за общую конфигурацию (в server/settings.py):
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
