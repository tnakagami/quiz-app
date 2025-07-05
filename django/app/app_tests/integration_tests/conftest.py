import pytest
from app_tests import factories
from account.models import RoleType

@pytest.fixture
def init_webtest(django_db_blocker, csrf_exempt_django_app):
  with django_db_blocker.unblock():
    owner, other = factories.UserFactory.create_batch(2, is_active=True, role=RoleType.GUEST)
  app = csrf_exempt_django_app
  users = {
    'owner': owner,
    'other': other,
  }

  return app, users

@pytest.fixture(scope='module', params=['superuser', 'manager', 'creator', 'guest'])
def get_users(django_db_blocker, request):
  patterns = {
    'superuser': {'is_active': True, 'is_staff': True, 'is_superuser': True, 'role': RoleType.GUEST},
    'manager': {'is_active': True, 'role': RoleType.MANAGER},
    'creator': {'is_active': True, 'role': RoleType.CREATOR},
    'guest': {'is_active': True, 'role': RoleType.GUEST},
  }
  key = request.param
  kwargs = patterns[key]
  # Get user instance
  with django_db_blocker.unblock():
    user = factories.UserFactory(**kwargs)

  return key, user