import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from app_tests import status
from account import views

UserModel = get_user_model()

@pytest.mark.account
@pytest.mark.view
@pytest.mark.parametrize([
  'timeout_val',
  'expected',
], [
  (5*60, 5*60),
  (10*60, 10*60),
], ids=[
  'is-default-value',
  'user-definition-value',
])
def test_check_get_timelimit_seconds(settings, timeout_val, expected):
  settings.ACTIVATION_TIMEOUT_SECONDS = timeout_val
  ret = views._get_timelimit_seconds()

  assert ret == expected

@pytest.mark.account
@pytest.mark.view
@pytest.mark.parametrize([
  'timeout_val',
  'expected',
], [
  (5*60, 5),
  (10*60, 10),
], ids=[
  'is-default-value',
  'user-definition-value',
])
def test_check_get_timelimit_minutes(settings, timeout_val, expected):
  settings.ACTIVATION_TIMEOUT_SECONDS = timeout_val
  ret = views._get_timelimit_minutes()

  assert ret == expected

@pytest.mark.account
@pytest.mark.view
def test_check_reset_timemout(settings):
  settings.PASSWORD_RESET_TIMEOUT = 4 * 60
  ret = views._get_password_reset_timeout_minutes()

  assert ret == 4

@pytest.mark.account
@pytest.mark.view
def test_index_view_get_access(client):
  url = reverse('account:alternative')
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.account
@pytest.mark.view
def test_login_view_get_access(client):
  url = reverse('account:login')
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK