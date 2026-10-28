"""Локальный запуск своей части, пока URL приложений коллег не созданы."""
from server.settings import *

ROOT_URLCONF = 'firuz.dev_urls'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'firuz' / 'db.sqlite3',
    },
}
