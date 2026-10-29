from server.settings import *

ROOT_URLCONF = 'simple.dev_urls'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'simple' / 'db.sqlite3',
    },
}
