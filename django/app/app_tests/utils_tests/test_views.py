import pytest
from django.urls import reverse
from app_tests import status, factories
from account.models import RoleType

@pytest.fixture(params=['superuser', 'manager', 'creator', 'guest', 'anonymous'], scope='module')
def get_users(django_db_blocker, request):
  patterns = {
    'superuser': {'is_active': True, 'role': RoleType.GUEST, 'is_staff': True, 'is_superuser': True},
    'manager':   {'is_active': True, 'role': RoleType.MANAGER},
    'creator':   {'is_active': True, 'role': RoleType.CREATOR},
    'guest':     {'is_active': True, 'role': RoleType.GUEST},
    'anonymous': {'is_active': False},
  }
  key = request.param
  kwargs = patterns[key]

  with django_db_blocker.unblock():
    user = factories.UserFactory(**kwargs)

  return key, user

@pytest.mark.utils
@pytest.mark.view
@pytest.mark.django_db
class TestUtilsView:
  index_url = reverse('utils:index')
  introduction_url = reverse('utils:introduction')

  def test_index_view_get_access(self, client, get_users):
    _, user = get_users
    client.force_login(user)
    response = client.get(self.index_url)

    assert response.status_code == status.HTTP_200_OK

  def test_introduction_view_get_access(self, client, get_users):
    _, user = get_users
    client.force_login(user)
    response = client.get(self.introduction_url)

    assert response.status_code == status.HTTP_200_OK

  def test_check_digest(self, mocker, client):
    mocker.patch('utils.views.get_digest', return_value='abc')
    response = client.get(self.index_url)
    digest = response.context['hash_value']

    assert digest == 'abc'