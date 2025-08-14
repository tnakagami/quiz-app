import pytest
from django.urls import reverse
from app_tests import factories
from passkey import models

@pytest.fixture
def mock_fido2server(mocker):
  class _AuthData:
    def __init__(self):
      self.credential_data = bytes('foo-bar', encoding='utf-8')

  class DummyServer:
    def __init__(self, *args, **kwargs):
      pass
    def register_begin(self, *args, **kwargs):
      data = {'id': 'hoge', 'publicKey': {'challenge': 'foo'}}
      state = {'result': 'ok', 'detail': ''}

      return data, state
    def register_complete(self, *args, **kwargs):
      return _AuthData()
    def authenticate_begin(self, *args, **kwargs):
      return self.register_begin(*args, **kwargs)
    def authenticate_complete(self, *args, **kwargs):
      return None

  mocker.patch('passkey.models.UserPasskey.get_server', return_value=DummyServer())

  return mocker

@pytest.mark.passkey
@pytest.mark.model
@pytest.mark.django_db
class TestUserPasskey:
  ajax_register_url = reverse('passkey:register_passkey')
  ajax_complete_url = reverse('passkey:complete_passkey_registration')
  ajax_auth_begin_url = reverse('passkey:begin_passkey_auth')

  def test_check_instance_type(self):
    passkey = factories.UserPasskeyFactory.build()

    assert isinstance(passkey, models.UserPasskey)

  @pytest.mark.parametrize([
    'platform_name',
  ], [
    ('Apple', ),
    ('Chrome on Apple', ),
    ('Google', ),
    ('Microsoft', ),
    ('Unknown', ),
  ], ids=lambda xs: str(xs))
  def test_check_str_method(self, get_test_user, platform_name):
    _, user = get_test_user
    passkey = factories.UserPasskeyFactory(user=user, platform=platform_name)
    expected = f'{user}({platform_name})'

    assert expected == str(passkey)

  @pytest.mark.parametrize([
    'is_same',
    'expected',
  ], [
    (True, True),
    (False, False),
  ], ids=[
    'same-user',
    'not-same-user',
  ])
  def test_check_update_permission(self, get_test_user, is_same, expected):
    _, user = get_test_user
    passkey = factories.UserPasskeyFactory(user=user)
    # Set login user
    if is_same:
      login_user = user
    else:
      login_user = factories.UserFactory(is_active=True)
    # Call target method
    can_update = passkey.has_update_permission(login_user)

    assert expected == can_update

  @pytest.mark.parametrize([
    'is_same',
    'is_enabled',
    'expected',
  ], [
    (True, True, False),
    (True, False, True),
    (False, True, False),
    (False, False, False),
  ], ids=[
    'same-user-and-enable',
    'same-user-and-disable',
    'not-same-user-and-enable',
    'not-same-user-and-disable',
  ])
  def test_check_delete_permission(self, get_test_user, is_same, is_enabled, expected):
    _, user = get_test_user
    passkey = factories.UserPasskeyFactory(user=user, is_enabled=is_enabled)
    # Set login user
    if is_same:
      login_user = user
    else:
      login_user = factories.UserFactory(is_active=True)
    # Call target method
    can_delete = passkey.has_delete_permission(login_user)

    assert expected == can_delete

  def test_get_credentials(self, mocker, get_test_user):
    mocker.patch('passkey.models.AttestedCredentialData', side_effect=['a', 'b', 'c'])
    _, user = get_test_user
    passkeys = factories.UserPasskeyFactory.create_batch(3, user=user)
    instance = models.UserPasskey(user=user)
    # Call target method
    credentials = instance.get_credentials()

    assert len(passkeys) == len(credentials)

  @pytest.mark.parametrize([
    'is_callable_server_id',
    'is_callable_server_name',
  ], [
    (False, False),
    (True, False),
    (False, True),
    (True, True),
  ], ids=[
    'cannot-call-both-id-and-name',
    'can-call-server-id',
    'can-call-server-name',
    'can-call-both-id-and-name',
  ])
  def test_get_server(self, settings, rf, is_callable_server_id, is_callable_server_name):
    from fido2.server import Fido2Server
    # Set server id
    if is_callable_server_id:
      expected_server_id = 'hogehoge-id'
      settings.FIDO_SERVER_ID = lambda request: expected_server_id
    else:
      expected_server_id = 'test-server-id'
      settings.FIDO_SERVER_ID = expected_server_id
    # Set server name
    if is_callable_server_name:
      expected_server_name = 'hogehoge-name'
      settings.FIDO_SERVER_NAME = lambda request: expected_server_name
    else:
      expected_server_name = 'test-server-name'
      settings.FIDO_SERVER_NAME = expected_server_name
    # Call target method
    request = rf.get(self.ajax_register_url)
    server = models.UserPasskey.get_server(request)

    assert isinstance(server, Fido2Server)

  @pytest.mark.parametrize([
    'user_agent',
    'expected',
  ], [
    # Apple
    ('Mozilla/5.0 (Macintosh; Intel Mac OS X 16_5) AppleWebKit/623.1.23 (KHTML, like Gecko) Version/16.5 Safari/623.1.23', 'Apple'),
    ('Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/623.1.23 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/623.1.23', 'Apple'),
    ('Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) AppleWebKit/623.1.23 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/623.1.23', 'Apple'),
    ('Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/623.1.23 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/623.1.23', 'Chrome on Apple'),
    # Windows
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/623.1.23 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/623.1.23', 'Microsoft'),
    # Android
    ('Mozilla/5.0 (Linux; Android 11) AppleWebKit/623.1.23 (KHTML, like Gecko) Chrome/123.4.5678.123 Mobile Safari/623.1.23', 'Google'),
    ('Mozilla/5.0 (Linux; Android 11; Pixel 4) AppleWebKit/623.1.23 (KHTML, like Gecko) Chrome/123.4.5678.123 Mobile Safari/623.1.23', 'Google'),
    ('Mozilla/5.0 (Linux; Android 11; Galaxy S) AppleWebKit/623.1.23 (KHTML, like Gecko) Chrome/123.4.5678.123 Mobile Safari/623.1.23', 'Google'),
  ], ids=[
    'mac-os',
    'ios',
    'ipad',
    'chrome-mac',
    'chrome-windows',
    'android-type1',
    'android-type2',
    'android-type3',
  ])
  def test_get_current_platform(self, rf, user_agent, expected):
    request = rf.get('/', HTTP_USER_AGENT=user_agent)
    platform = models.UserPasskey.get_current_platform(request)

    assert expected == platform

  def test_register_begin(self, rf, mock_fido2server, get_test_user):
    _ = mock_fido2server
    _, user = get_test_user
    request = rf.get(self.ajax_register_url)
    request.session = {}
    instance = models.UserPasskey(user=user)
    data = instance.register_begin(request)
    estimated = dict(data)

    assert all([key in ['id', 'publicKey'] for key in estimated.keys()])
    assert estimated['id'] == 'hoge'
    assert estimated['publicKey'] == {'challenge': 'foo'}
    assert 'fido2_state' in request.session
    assert request.session['fido2_state'] == {'result': 'ok', 'detail': ''}

  def test_valid_register_complete(self, rf, mock_fido2server, get_test_user):
    mocker = mock_fido2server
    mocker.patch('passkey.models.UserPasskey.get_current_platform', return_value='Microsoft')
    _, user = get_test_user
    params = {
      'id': 'hogehoge-0x123456-id',
      'key_name': 'test-key',
    }
    request = rf.post(self.ajax_complete_url, data=params, content_type='application/json')
    request.session = {'fido2_state': {'result': 'ok', 'detail': ''}}
    # Call target method
    instance = models.UserPasskey(user=user)
    status = instance.register_complete(request)
    estimated = dict(status)
    instance = models.UserPasskey.objects.get(credential_id=params['id'])

    assert all([key in ['code', 'message'] for key in estimated.keys()])
    assert estimated['code'] == 200
    assert instance.name == 'test-key'
    assert instance.is_enabled
    assert instance.platform == 'Microsoft'

  @pytest.mark.parametrize([
    'pattern',
  ], [
    ('no-session-data', ),
    ('has-error', ),
  ], ids=lambda xs: str(xs))
  def test_invalid_register_complete(self, rf, mock_fido2server, get_test_user, pattern):
    mocker = mock_fido2server
    _, user = get_test_user
    params = {
      'id': 'hogehoge-0x123456-id',
      'key_name': 'test-key',
    }
    request = rf.post(self.ajax_complete_url, data=params)
    # Customize data based on pattern
    if pattern == 'has-error':
      request.session = {'fido2_state': {'result': 'ok', 'detail': ''}}
      mocker.patch('passkey.models.UserPasskey.get_current_platform', side_effect=Exception('Error'))
      status_code = 500
      err_msg = 'Error on server, please try again later'
    else:
      request.session = {}
      status_code = 401
      err_msg = 'FIDO Status can’t be found, please try again'
    # Call target method
    instance = models.UserPasskey(user=user)
    status = instance.register_complete(request)
    estimated = dict(status)

    assert all([key in ['code', 'message'] for key in estimated.keys()])
    assert estimated['code'] == status_code
    assert estimated['message'] == err_msg

  @pytest.mark.parametrize([
    'is_authenticated',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'is-authenticated',
    'is-not-authenticated',
  ])
  def test_check_auth_begin(self, rf, mock_fido2server, get_test_user, is_authenticated):
    class DummyUser:
      def __init__(self):
        self.is_authenticated = False

    mocker = mock_fido2server
    mocker.patch('passkey.models.UserPasskey.get_credentials', return_value=['a', 'b'])
    _, user = get_test_user
    request = rf.get(self.ajax_auth_begin_url)
    if is_authenticated:
      request.user = user
    else:
      request.user = DummyUser()
    request.session = {}
    # Call target method
    data = models.UserPasskey.auth_begin(request)
    estimated = dict(data)

    assert estimated == {'id': 'hoge', 'publicKey': {'challenge': 'foo'}}
    assert request.session['fido2_state'] == {'result': 'ok', 'detail': ''}

  def test_valid_auth_complete(self, rf, mock_fido2server, get_test_user):
    mocker = mock_fido2server
    mocker.patch('passkey.models.AttestedCredentialData', return_value='hoge')
    mocker.patch('passkey.models.UserPasskey.get_current_platform', return_value='Microsoft')
    _, user = get_test_user
    credential_id = 'test-id-for-valid-auth-complete'
    _ = factories.UserPasskeyFactory(
      user=user,
      credential_id=credential_id,
      is_enabled=True,
      platform='Unknown',
    )
    params = {
      'passkeys': {
        'id': credential_id,
      },
    }
    mocker.patch('passkey.models.json.loads', return_value=params['passkeys'])
    request = rf.post('/', data=params)
    request.session = {'fido2_state': {'result': 'ok', 'detail': ''}}
    # Call target method
    output = models.UserPasskey.auth_complete(request)
    passkey = request.session.get('passkey')
    instance = models.UserPasskey.objects.get(credential_id=credential_id, is_enabled=True)

    assert output.pk == user.pk
    assert passkey is not None
    assert passkey['passkey']
    assert passkey['name'] == instance.name
    assert passkey['id'] == instance.pk
    assert passkey['platform'] == instance.platform
    assert not passkey['cross_platform']

  def test_invalid_credential_id_in_auth_complete(self, mocker, rf, get_test_user):
    _, user = get_test_user
    credential_id = 'invalid-id-in-auth-complete'
    params = {
      'passkeys': {
        'id': credential_id,
      },
    }
    mocker.patch('passkey.models.json.loads', return_value=params['passkeys'])
    request = rf.post('/', data=params)
    # Call target method
    output = models.UserPasskey.auth_complete(request)

    assert output is None

  @pytest.mark.parametrize([
    'exception_type',
  ], [
    (ValueError, ),
    (models.UserPasskey.DoesNotExist, ),
    (Exception, ),
  ], ids=[
    'value-error',
    'database-error',
    'has-exception',
  ])
  def test_check_raising_exception_in_auth_complete(self, rf, mock_fido2server, get_test_user, exception_type):
    _, user = get_test_user
    params = {
      'passkeys': {
        'id': 'hgoehoge',
      },
    }
    mocker = mock_fido2server
    mocker.patch('passkey.models.UserPasskey.objects.get', return_value=factories.UserPasskeyFactory(user=user))
    mocker.patch('passkey.models.AttestedCredentialData', side_effect=exception_type('Error'))
    mocker.patch('passkey.models.json.loads', return_value=params['passkeys'])
    request = rf.post('/', data=params)
    # Call target method
    output = models.UserPasskey.auth_complete(request)

    assert output is None