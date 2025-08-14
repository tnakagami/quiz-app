import pytest
from django.urls import reverse
from app_tests import status, factories
from app_tests.passkey_tests import SoftWebauthnDevice
from passkey import views, models
import json

@pytest.mark.passkey
@pytest.mark.view
@pytest.mark.django_db
class TestPasskeyView:
  list_view_url = reverse('passkey:passkey_list')
  update_view_url = lambda _self, pk: reverse('passkey:update_passkey', kwargs={'pk': pk})
  delete_view_url = lambda _self, pk: reverse('passkey:delete_passkey', kwargs={'pk': pk})

  def test_get_access_to_listpage(self, get_users, client):
    _, user = get_users
    client.force_login(user)
    response = client.get(self.list_view_url)

    assert response.status_code == status.HTTP_200_OK

  def test_queryset_method_in_listpage(self, rf, get_users):
    _, user = get_users
    others = factories.UserFactory.create_batch(3, is_active=True)
    # Create several passkeys
    _ = factories.UserPasskeyFactory(user=user,      is_enabled=True)
    _ = factories.UserPasskeyFactory(user=user,      is_enabled=False)
    _ = factories.UserPasskeyFactory(user=others[0], is_enabled=True)
    _ = factories.UserPasskeyFactory(user=others[1], is_enabled=True)
    _ = factories.UserPasskeyFactory(user=others[1], is_enabled=False)
    _ = factories.UserPasskeyFactory(user=others[2], is_enabled=True)
    # Call `get_queryset` method
    request = rf.get(self.list_view_url)
    request.user = user
    view = views.PasskeyListPage()
    view.setup(request)
    queryset = view.get_queryset()

    assert queryset.count() == 2

  def test_get_access_to_updatepage(self, get_users, client):
    _, user = get_users
    instance = factories.UserPasskeyFactory(user=user, is_enabled=True)
    url = self.update_view_url(instance.pk)
    client.force_login(user)
    response = client.get(url)

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

  @pytest.mark.parametrize([
    'is_enabled',
    'expected',
  ], [
    (True, False),
    (False, True),
  ], ids=[
    'from-enable-to-disable',
    'from-disable-to-enable',
  ])
  def test_post_access_to_updatepage(self, get_users, client, is_enabled, expected):
    _, user = get_users
    client.force_login(user)
    original = factories.UserPasskeyFactory(user=user, is_enabled=is_enabled)
    url = self.update_view_url(original.pk)
    response = client.post(url, data={})
    instance = models.UserPasskey.objects.get(pk=original.pk)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_view_url
    assert instance.is_enabled == expected

  def test_invalid_post_request_in_updatepage(self, get_users, get_test_user, client):
    _, user = get_users
    _, tester = get_test_user
    client.force_login(user)
    other_member_instance = factories.UserPasskeyFactory(user=tester, is_enabled=True)
    url = self.update_view_url(other_member_instance.pk)
    response = client.post(url, data={})

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_get_access_to_deletepage(self, get_users, client):
    _, user = get_users
    instance = factories.UserPasskeyFactory(user=user, is_enabled=False)
    url = self.delete_view_url(instance.pk)
    client.force_login(user)
    response = client.get(url)

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

  def test_post_access_to_deletepage(self, get_users, client):
    _, user = get_users
    instance = factories.UserPasskeyFactory(user=user, is_enabled=False)
    url = self.delete_view_url(instance.pk)
    client.force_login(user)
    response = client.post(url)
    queryset = models.UserPasskey.objects.filter(pk__in=[instance.pk])

    assert response.status_code == status.HTTP_302_FOUND
    assert queryset.count() == 0

  @pytest.mark.parametrize([
    'is_same',
    'is_enabled',
  ], [
    (True, True),
    (False, False),
  ], ids=[
    'is-enable',
    'the-other-user',
  ])
  def test_invalid_post_request_in_deletepage(self, get_users, get_test_user, client, is_same, is_enabled):
    _, user = get_users
    _, tester = get_test_user
    target = user if is_same else tester
    instance = factories.UserPasskeyFactory(user=target, is_enabled=is_enabled)
    url = self.delete_view_url(instance.pk)
    client.force_login(user)
    response = client.post(url)
    queryset = models.UserPasskey.objects.filter(pk__in=[instance.pk])

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert queryset.count() == 1

@pytest.mark.passkey
@pytest.mark.view
@pytest.mark.django_db
class TestPasskeyRegisterationAndAuthentication:
  ajax_register_url = reverse('passkey:register_passkey')
  ajax_complete_url = reverse('passkey:complete_passkey_registration')
  ajax_auth_begin_url = reverse('passkey:begin_passkey_auth')
  login_url = reverse('account:login')

  def test_passkey_registration(self, get_test_user, client):
    _, user = get_test_user
    client.force_login(user)
    # Request passkey registration
    register_response = client.get(self.ajax_register_url, secure=True)
    jsonData = json.loads(register_response.content)
    jsonData['publicKey']['challenge'] = jsonData['publicKey']['challenge'].encode('ascii')
    target_id = jsonData['publicKey']['rp']['id']
    soft_device = SoftWebauthnDevice()
    credentials = soft_device.create(jsonData, f'https://{target_id}')
    credentials['key_name'] = 'test_key'
    # Request passkey registration completation
    complete_response = client.post(
      self.ajax_complete_url,
      data=json.dumps(credentials),
      headers={'USER_AGENT': ''},
      HTTP_USER_AGENT='',
      content_type='application/json',
      secure=True,
    )

    try:
      output = json.loads(complete_response.content)
    except Exception as ex:
      pytest.fail(f'Unexpected Error: {ex}')
    keys = output.keys()
    instance = models.UserPasskey.objects.get(credential_id=credentials['id'])

    assert register_response.status_code == status.HTTP_200_OK
    assert complete_response.status_code == status.HTTP_200_OK
    assert all([key in ['code', 'message'] for key in keys])
    assert output['code'] == 200
    assert output['message'] == 'OK'
    assert instance.name == 'test_key'

  def test_set_key_name_automatically(self, get_test_user, client):
    _, user = get_test_user
    client.force_login(user)
    # Request passkey registration
    register_response = client.get(self.ajax_register_url, secure=True)
    jsonData = json.loads(register_response.content)
    jsonData['publicKey']['challenge'] = jsonData['publicKey']['challenge'].encode('ascii')
    target_id = jsonData['publicKey']['rp']['id']
    soft_device = SoftWebauthnDevice()
    credentials = soft_device.create(jsonData, f'https://{target_id}')
    # Request passkey registration completation
    user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 16_5) AppleWebKit/623.1.23 (KHTML, like Gecko) Version/16.5 Safari/623.1.23'
    complete_response = client.post(
      self.ajax_complete_url,
      data=json.dumps(credentials),
      HTTP_USER_AGENT=user_agent,
      content_type='application/json',
      secure=True,
    )

    try:
      output = json.loads(complete_response.content)
    except Exception as ex:
      pytest.fail(f'Unexpected Error: {ex}')
    keys = output.keys()
    instance = models.UserPasskey.objects.get(credential_id=credentials['id'])

    assert register_response.status_code == status.HTTP_200_OK
    assert complete_response.status_code == status.HTTP_200_OK
    assert all([key in ['code', 'message'] for key in keys])
    assert output['code'] == 200
    assert output['message'] == 'OK'
    assert instance.name == 'Apple'

  def test_invalid_complete_request_without_session(self, get_users, client):
    _, user = get_users
    client.force_login(user)
    credentials = {
      'key_name': 'test_key',
    }
    response = client.post(
      self.ajax_complete_url,
      data=json.dumps(credentials),
      headers={'USER_AGENT': ''},
      HTTP_USER_AGENT='',
      content_type='application/json',
      secure=True,
    )

    try:
      output = json.loads(response.content)
    except Exception as ex:
      pytest.fail(f'Unexpected Error: {ex}')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert all([key in ['code', 'message'] for key in output.keys()])
    assert output['code'] == status.HTTP_401_UNAUTHORIZED
    assert output['message'] == 'FIDO Status can’t be found, please try again'

  def test_invalid_complete_request_with_error(self, mocker, get_users, client):
    _, user = get_users
    client.force_login(user)
    # Request passkey registration
    register_response = client.get(self.ajax_register_url, secure=True)
    jsonData = json.loads(register_response.content)
    jsonData['publicKey']['challenge'] = jsonData['publicKey']['challenge'].encode('ascii')
    target_id = jsonData['publicKey']['rp']['id']
    soft_device = SoftWebauthnDevice()
    credentials = soft_device.create(jsonData, f'https://{target_id}')
    credentials['key_name'] = 'test_key'
    # Request passkey registration completation
    mocker.patch('passkey.models.UserPasskey.get_server', side_effect=Exception('Error'))
    complete_response = client.post(
      self.ajax_complete_url,
      data=json.dumps(credentials),
      headers={'USER_AGENT': ''},
      HTTP_USER_AGENT='',
      content_type='application/json',
      secure=True,
    )

    try:
      output = json.loads(complete_response.content)
    except Exception as ex:
      pytest.fail(f'Unexpected Error: {ex}')
    keys = output.keys()

    assert register_response.status_code == status.HTTP_200_OK
    assert complete_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert all([key in ['code', 'message'] for key in keys])
    assert output['code'] == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert output['message'] == 'Error on server, please try again later'

  def test_login_process_with_passkey(self, get_users, client):
    _, user = get_users
    client.force_login(user)
    # Request passkey registration
    response = client.get(self.ajax_register_url, secure=True)
    jsonData = json.loads(response.content)
    jsonData['publicKey']['challenge'] = jsonData['publicKey']['challenge'].encode('ascii')
    target_id = jsonData['publicKey']['rp']['id']
    soft_device = SoftWebauthnDevice()
    credentials = soft_device.create(jsonData, f'https://{target_id}')
    credentials['key_name'] = 'test-machine'
    # Request passkey registration completation
    _ = client.post(
      self.ajax_complete_url,
      data=json.dumps(credentials),
      headers={'USER_AGENT': ''},
      HTTP_USER_AGENT='',
      content_type='application/json',
      secure=True,
    )
    # Logout
    client.logout()
    auth_begin_response = client.get(self.ajax_auth_begin_url, secure=True)
    jsonData = json.loads(auth_begin_response.content)
    jsonData['publicKey']['challenge'] = jsonData['publicKey']['challenge'].encode('ascii')
    target_id = jsonData['publicKey']['rpId']
    assertion = soft_device.get(jsonData, f'https://{target_id}')
    params = {
      'passkeys': json.dumps(assertion),
      'username': '',
      'password': '',
    }
    login_response = client.post(
      self.login_url,
      data=params,
      headers={'USER_AGENT': ''},
      HTTP_USER_AGENT='',
      follow=True,
      secure=True,
    )

    assert auth_begin_response.status_code == status.HTTP_200_OK
    assert login_response.status_code == status.HTTP_200_OK
    assert client.session.get('passkey', {}).get('passkey', False)
    assert client.session.get('passkey', {}).get('name') == 'test-machine'