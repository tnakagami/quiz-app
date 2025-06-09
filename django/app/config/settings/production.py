import os
from .base import *

DEBUG = False
ALLOWED_HOSTS = os.getenv('BACKEND_ALLOWED_HOSTS').split(',')
CSRF_TRUSTED_ORIGINS = os.getenv('DJANGO_TRUSTED_ORIGINS').split(',')
