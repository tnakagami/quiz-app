"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from channels.routing import ProtocolTypeRouter
from .define_module import setup_default_setting
from django.core.asgi import get_asgi_application

setup_default_setting()
# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app  = get_asgi_application()

application = ProtocolTypeRouter({
  'http': django_asgi_app,
})