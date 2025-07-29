import pytest
from app_tests import factories
from account.models import RoleType

@pytest.fixture(scope='module')
def get_guest(django_db_blocker):
  with django_db_blocker.unblock():
    user = factories.UserFactory(is_active=True, role=RoleType.GUEST)

  return user

@pytest.fixture(scope='module')
def get_creator(django_db_blocker):
  with django_db_blocker.unblock():
    user = factories.UserFactory(is_active=True, role=RoleType.CREATOR)

  return user

@pytest.fixture(scope='module')
def get_manager(django_db_blocker):
  with django_db_blocker.unblock():
    user = factories.UserFactory(is_active=True, role=RoleType.MANAGER)

  return user

@pytest.fixture(scope='module')
def get_superuser(django_db_blocker):
  with django_db_blocker.unblock():
    user = factories.UserFactory(is_active=True, role=RoleType.GUEST, is_staff=True, is_superuser=True)

  return user

@pytest.fixture(scope='module')
def get_friends(django_db_blocker):
  with django_db_blocker.unblock():
    friends = list(factories.UserFactory.create_batch(3, is_active=True, role=RoleType.GUEST))

  return friends

@pytest.fixture(params=['superuser', 'manager', 'creator', 'guest'], scope='module')
def get_users(request, get_guest, get_creator, get_manager, get_superuser):
  patterns = {
    'superuser': get_superuser,
    'manager': get_manager,
    'creator': get_creator,
    'guest': get_guest,
  }
  key = request.param
  user = patterns[key]

  return key, user

@pytest.fixture(params=['superuser', 'manager'], scope='class')
def get_has_manager_role_user(request, get_manager, get_superuser):
  patterns = {
    'superuser': get_superuser,
    'manager': get_manager,
  }
  key = request.param
  user = patterns[key]

  return key, user

@pytest.fixture(params=['superuser', 'manager', 'creator'], scope='module')
def get_editors(request, get_creator, get_manager, get_superuser):
  key = request.param
  patterns = {
    'superuser': get_superuser,
    'manager': get_manager,
    'creator': get_creator,
  }
  user = patterns[key]

  return key, user

@pytest.fixture(params=['creator', 'guest'], scope='module')
def get_players(request, get_guest, get_creator):
  key = request.param
  patterns = {
    'creator': get_creator,
    'guest': get_guest,
  }
  user = patterns[key]

  return key, user