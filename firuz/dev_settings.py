from server.settings import *

ROOT_URLCONF = 'firuz.dev_urls'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'firuz' / 'media'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'firuz' / 'db.sqlite3',
    },
}
