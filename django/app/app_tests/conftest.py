import pytest

@pytest.fixture(scope='session', autouse=True)
def django_db_setup(django_db_setup):
  pass

@pytest.fixture(autouse=True)
def setup_django(settings):
  settings.LANGUAGE_CODE = 'en'
  settings.TIME_ZONE = 'Asia/Tokyo'
  settings.HASH_SALT = 'send-salt-to-relevant-member'
  settings.EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
  settings.SESSION_COOKIE_SECURE = False
  settings.CSRF_COOKIE_SECURE = False
  settings.SESSION_EXPIRE_AT_BROWSER_CLOSE = False

@pytest.fixture
def csrf_exempt_django_app(django_app_factory):
  app = django_app_factory(csrf_checks=False)

  return app