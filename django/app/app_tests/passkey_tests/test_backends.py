import pytest
from django.urls import reverse
from app_tests import factories
from passkey import backend

@pytest.mark.passkey
@pytest.mark.model
@pytest.mark.django_db
class TestPasskeyModelBackend:
  ajax_auth_url = reverse('passkey:begin_passkey_auth')

  def test_no_request_instance(self, get_test_user):
    raw_passwd, user = get_test_user
    instance = backend.PasskeyModelBackend()

    with pytest.raises(Exception) as ex:
      instance.authenticate(request=None, username=user.email, password=raw_passwd)

    assert '`request` is required for passkey.backend.PasskeyModelBackend' in ex.value.args

  def test_not_add_passkey(self, rf):
    instance = backend.PasskeyModelBackend()
    params = {
      'username': '',
      'password': '',
    }
    request = rf.post(self.ajax_auth_url, data=params)

    with pytest.raises(Exception) as ex:
      instance.authenticate(request=request, **params)

    assert '`passkeys` are required in request.POST' in ex.value.args

  def test_valid_login(self, mocker, rf, get_test_user):
    from django.contrib.auth import get_user_model
    _, user = get_test_user
    mocker.patch('passkey.models.UserPasskey.auth_complete', return_value=user)
    params = {'username': '', 'password': '', 'passkeys': 'dummy-passkey'}
    request = rf.post(self.ajax_auth_url, data=params)
    instance = backend.PasskeyModelBackend()
    logged_in_user = instance.authenticate(request=request)

    assert logged_in_user is not None
    assert isinstance(logged_in_user, get_user_model())

  @pytest.fixture(params=['empty-username', 'empty-password', 'no-data'])
  def get_backend_input(self, request, rf, get_test_user):
    raw_passwd, user = get_test_user
    patterns = {
      'empty-username': {'username': '', 'password': raw_passwd, 'passkeys': ''},
      'empty-password': {'username': user.email, 'password': '', 'passkeys': ''},
      'no-data': {'username': '', 'password': '', 'passkeys': ''},
    }
    key = request.param
    data = patterns[key]
    # Create output values
    req = rf.post(self.ajax_auth_url, data=data)
    params = {
      'username': data['username'],
      'password': data['password'],
    }

    return req, params

  def test_check_invalid_login_pattern(self, get_backend_input):
    request, params = get_backend_input
    instance = backend.PasskeyModelBackend()
    user = instance.authenticate(request=request, **params)

    assert user is None