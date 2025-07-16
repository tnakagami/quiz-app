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