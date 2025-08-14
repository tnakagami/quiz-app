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
    #
    # Apple
    #
    ### iOS and iPhone
    ('Mozilla/5.0 (iPhone; CPU iPhone OS 5_1 like Mac OS X) AppleWebKit/534.46 (KHTML, like Gecko) Version/5.1 Opera/123.4.5', 'Apple'),
    ### iOS and iPad
    ('Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) AppleWebKit/623.1.23 (KHTML, like Gecko) Version/16.5 Opera/123.4.5', 'Apple'),
    ### iOS and iPod
    ('Mozilla/5.0 (iPod touch; CPU iPhone OS 12_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Opera/123.4.5', 'Apple'),
    ### AppleTV
    ('AppleTV3,1/6.0.1 (10A831)', 'Apple'),
    ### iOS
    ('Mozilla/5.0 (XXX; CPU OS 5_1 like Mac OS X) AppleWebKit/534.46 (KHTML, like Gecko) Version/5.1 Opera/123.4.5', 'Apple'),
    ### Mac OS X
    ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.13+ (KHTML, like Gecko) Version/5.1.7 Opera/123.4.5', 'Apple'),
    ### Chrome Mobile iOS
    ('Mozilla/5.0 (XXX; CPU YYY 1_2_3 like ZZZ) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/139.0.7258.76 Opera/123.4.5', 'Apple'),
    ### Safari
    ('Mozilla/5.0 (XXX; CPU YYY 12_0 like ZZZ) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1', 'Apple'),
    #
    # Amazon
    #
    ### Kindle
    ('Mozilla/5.0 (Linux; U; Android 2.3.4; en-us; Kindle Fire Build/GINGERBREAD) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1', 'Amazon'),
    ('Mozilla/5.0 (Linux; U; Android 2.3.4; en-us; Silk/1.0.146.3-Gen4_12000410) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1 Silk-Accelerated=true', 'Amazon'),
    ### Amazon Fire TV
    ('fuboTV/2.0.2 (Linux;Android 5.1.1; AFTT Build/LVY48F) FuboPlayer/1.0.2.4', 'Amazon'),
    ('SPMC/16.3-0 (Linux; Android 5.1.1; AFTM Build/LVY48F) Kodi_Fork_SPMC/1.0 Android/5.1.1', 'Amazon'),
    ('Kodi/16.1 (Linux; Android 5.1.1; AFTB Build/LVY48F) Android/5.1.1 Sys_CPU/armv7l', 'Amazon'),
    ('Mozilla/5.0 (Linux; Android 5.1.1; AFTS Build/LVY48F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.83 Mobile Safari/537.36', 'Amazon'),
    ### Amazon
    ('Amazon CloudFront', 'Amazon'),
    #
    # Windows
    #
    ### Windows PC
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/623.1.23 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/623.1.23', 'Microsoft'),
    ### Windows Phone
    ('Mozilla/5.0 (compatible; MSIE 9.0; Windows Phone OS 10.5; Android 4.2.1; Trident/5.0; IEMobile/9.0; SAMSUNG; SGH-i917)', 'Microsoft'),
    ### Windows RT
    ('Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; ARM; Trident/6.0)', 'Microsoft'),
    #
    # Android
    #
    ### Normal Android
    ('Mozilla/5.0 (Linux; Android 11) AppleWebKit/623.1.23 (KHTML, like Gecko) Chrome/123.4.5678.123 Mobile Safari/623.1.23', 'Google'),
    ### PC site version of Android Chrome
    ('Mozilla/5.0 (X11; Linux x86_64)  AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.105 Safari/537.36', 'Google'),
    ### Chrome OS
    ('Mozilla/5.0 (X11; CrOS x86_64 7520.63.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.106 Safari/537.36', 'Google'),
    #
    # Unknown
    #
    ('Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:15.0) Gecko/20100101 Chrome/72.0.3626.105', 'Unknown'),
  ], ids=[
    # Apple
    'iPhone-iOS',
    'iPad-iOS',
    'iPod-iOS',
    'AppleTV',
    'iOS',
    'Mac-OS-X',
    'Chrome-Mobile-iOS',
    'Safari',
    # Amazon
    'Kindle-Fire',
    'Kindle-Silk',
    'Fire-TV(AFTT)',
    'Fire-TV(AFTM)',
    'Fire-TV(AFTB)',
    'Fire-TV(AFTS)',
    'Amazon-CloudFront',
    # Windows
    'Windows-PC',
    'Windows-Phone',
    'Windows-RT',
    # Android
    'Normal-Android',
    'PC-site-Android',
    'Chrome-OS',
    # Unknown
    'Unknown',
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