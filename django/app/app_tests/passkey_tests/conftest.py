import pytest
from django.contrib.auth import get_user_model
from app_tests import factories
from account.models import RoleType

UserModel = get_user_model()

@pytest.fixture(scope='module', params=[
  'superuser',
  'normal-manager',
  'normal-creator',
  'normal-guest',
], ids=lambda xs: str(xs))
def get_users(django_db_blocker, request):
  with django_db_blocker.unblock():
    _user_table = {
      'superuser': factories.UserFactory(is_active=True, is_staff=True, is_superuser=True, role=RoleType.GUEST),
      'normal-manager': factories.UserFactory(is_active=True, role=RoleType.MANAGER),
      'normal-creator': factories.UserFactory(is_active=True, role=RoleType.CREATOR),
      'normal-guest': factories.UserFactory(is_active=True, role=RoleType.GUEST),
    }
  key = request.param
  user = _user_table[key]

  return key, user

@pytest.fixture(scope='module')
def get_test_user(django_db_blocker):
  with django_db_blocker.unblock():
    email = 'test-user@passkey.local'
    raw_password = 'hoge@OK123-passkey'
    # Get or create specific user
    try:
      user = UserModel.objects.get(email=email)
    except:
      user = factories.UserFactory(is_active=True, email=email, screen_name='test-user', role=RoleType.GUEST)
    user.set_password(raw_password)
    user.save()

  return raw_password, user