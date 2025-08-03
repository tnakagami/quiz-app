import pytest
from django.utils import timezone, dateformat
from app_tests import factories
from account.models import RoleType
from quiz.models import Genre

@pytest.fixture(scope='module')
def get_genres(django_db_blocker):
  with django_db_blocker.unblock():
    genres = []

    for idx in range(8):
      output = dateformat.format(timezone.now(), 'Ymd-His.u')
      name = f'quiz{idx}-{output}'

      try:
        instance = Genre.objects.get(name=name)
      except:
        instance = factories.GenreFactory(name=name, is_enabled=True)
      genres += [instance]

  return genres

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

@pytest.fixture(scope='module', params=['superuser', 'manager', 'creator'])
def get_has_creator_role_users(get_superuser, get_manager, get_creator, request):
  key = request.param
  patterns = {
    'superuser': get_superuser,
    'manager': get_manager,
    'creator': get_creator,
  }
  user = patterns[key]

  return key, user

@pytest.fixture(scope='module', params=['manager', 'creator'])
def get_editors(get_manager, get_creator, request):
  key = request.param

  if key == 'manager':
    user = get_manager
  else:
    user = get_creator

  return key, user

@pytest.fixture(scope='module', params=['guest', 'creator'])
def get_players(get_guest, get_creator, request):
  key = request.param

  if key == 'guest':
    user = get_guest
  else:
    user = get_creator

  return key, user

@pytest.fixture(scope='module', params=['superuser', 'manager', 'creator', 'guest'])
def get_users(get_superuser, get_manager, get_creator, get_guest, request):
  patterns = {
    'superuser': get_superuser,
    'manager': get_manager,
    'creator': get_creator,
    'guest': get_guest,
  }
  key = request.param
  user = patterns[key]

  return key, user

@pytest.fixture(scope='module', params=['superuser', 'manager', 'creator', 'guest', 'owner'])
def get_members_with_owner(get_superuser, get_manager, get_creator, get_guest, request):
  def inner(role):
    key = request.param
    patterns = {
      'superuser': get_superuser,
      'manager': get_manager,
      'creator': get_creator,
      'guest': get_guest,
    }
    if key == 'owner':
      if role == RoleType.MANAGER:
        user = patterns['manager']
      elif role == RoleType.CREATOR:
        user = patterns['creator']
      else:
        user = patterns['guest']
    else:
      user = patterns[key]

    return key, user

  return inner