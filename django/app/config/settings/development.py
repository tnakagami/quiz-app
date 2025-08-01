import os
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = os.getenv('DJANGO_TRUSTED_ORIGINS').split(',')
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
CORS_ALLOW_ALL_ORIGINS = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        'TEST': {
            'NAME': 'test_db.sqlite3',
        },
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'