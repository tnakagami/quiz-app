"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from .define_module import setup_default_setting
from django.core.asgi import get_asgi_application

setup_default_setting()
application = get_asgi_application()
