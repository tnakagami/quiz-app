import pytest
from dataclasses import dataclass
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.urls import reverse
from app_tests import (
  status,
  factories,
  g_generate_item,
  g_compare_options,
)
from account import views, models
import json

UserModel = get_user_model()

@dataclass
class UserInfo:
  email: str
  password: str
  user: UserModel | None

@pytest.fixture
def init_records(django_db_blocker):
  hoge_guest = {
    'email': 'hoge@guest.com',
    'password': 'a1H-2oG@3eF#',
  }
  foo_creator = {
    'email': 'foo@creator.com',
    'password': 'h2o!nH3@foo+',
  }
  bar_manager = {
    'email': 'bar@manager.com',
    'password': 'So4@Easy3+Mngr',
  }
  not_active_user = {
    'email': 'not-active@none.com',
    'password': 'cann0t-use-this-Account',
  }
  someone = {
    'email': 'someone@none.com',
    'password': 'nobody+knows-No.0x02',
  }

  with django_db_blocker.unblock():
    users = [
      UserInfo(**hoge_guest, user=UserModel.objects.create_user(is_active=True, role=models.RoleType.GUEST, **hoge_guest)),
      UserInfo(**foo_creator, user=UserModel.objects.create_user(is_active=True, role=models.RoleType.CREATOR, **foo_creator)),
      UserInfo(**bar_manager, user=UserModel.objects.create_user(is_active=True, role=models.RoleType.MANAGER, **bar_manager)),
      UserInfo(**not_active_user, user=UserModel.objects.create_user(**not_active_user)),
      UserInfo(**someone, user=None),
    ]

  return users

# ======================
# = Index/Login/Logout =
# ======================
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

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_login_view_post_access(init_records, client):
  instance = init_records[0]
  params = {
    'email': instance.email,
    'password': instance.password,
  }
  url = reverse('account:login')
  response = client.post(url, params)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_logout_page(init_records, client):
  user = init_records[0].user
  client.force_login(user)
  url = reverse('account:logout')
  response = client.post(url)

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == reverse('utils:index')

# ============================
# = Show/Update user profile =
# ============================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_with_authentication_for_user_profile(init_records, client):
  user = init_records[0].user
  url = reverse('account:user_profile')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_without_authentication_for_user_profile(init_records, client):
  user = init_records[0].user
  url = reverse('account:user_profile')
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_access_to_update_user_profile_page(init_records, client):
  user = init_records[0].user
  url = reverse('account:update_profile')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_update_user_profile(init_records, client):
  user = init_records[0].user
  new_name = 'new-name'
  url = reverse('account:update_profile')
  client.force_login(user)
  response = client.post(url, data={'screen_name': new_name})
  modified_user = UserModel.objects.get(pk=user.pk)

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == reverse('account:user_profile')
  assert modified_user.screen_name == new_name

# ========================
# = Account registration =
# ========================
@pytest.fixture
def get_create_account_url():
  return reverse('account:create_account')

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'http_method',
  'args',
], [
  ('get', None),
  ('post', {'email': 'ho@ge.com', 'password1': 'hoge2@foo3Bar0', 'password2': 'hoge2@foo3Bar0', 'hash_sign': 'hoge'}),
], ids=[
  'call-get',
  'call-post',
])
def test_invalid_access_of_create_account_page(init_records, client, get_create_account_url, http_method, args):
  funcs = {
    'get': lambda url, params: client.get(url),
    'post': lambda url, params: client.post(url, data=params),
  }
  user = init_records[0].user
  url = get_create_account_url
  # Force login
  client.force_login(user)
  caller = funcs[http_method]
  response = caller(url, args)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
def test_valid_get_access_of_create_account_page(client, get_create_account_url):
  url = get_create_account_url
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.fixture(params=[
  'invalid-digest',
  'email-is-empty',
  'invalid-email-length',
  'password1-is-empty',
  'password2-is-empty',
  'wrong-password',
  'weak-password',
  'invalid-screen-name-length',
])
def get_input_patterns_for_create_account_page(request):
  original = {
    'email': 'ho@ge.com',
    'password1': 'hoge2@foo3Bar0',
    'password2': 'hoge2@foo3Bar0',
    'screen_name': 's-hoge',
    'hash_sign': 'hoge',
  }
  clone_node = {key: val for key, val in original.items()}

  if request.param == 'invalid-digest':
    clone_node['hash_sign'] = 'foo-bar'
    data = (clone_node, 'Invalid a digest value.')
  elif request.param == 'email-is-empty':
    del clone_node['email']
    data = (clone_node, 'This field is required')
  elif request.param == 'invalid-email-length':
    clone_node['email'] = '{}@hoge.com'.format('1'*120)
    data = (clone_node, 'Ensure this value has at most 128 character')
  elif request.param == 'password1-is-empty':
    del clone_node['password1']
    data = (clone_node, 'This field is required')
  elif request.param == 'password2-is-empty':
    del clone_node['password2']
    data = (clone_node, 'This field is required')
  elif request.param == 'wrong-password':
    clone_node['password2'] = clone_node['password1'] + 'abc'
    data = (clone_node, 'The two password fields didn’t match')
  elif request.param == 'weak-password':
    clone_node['password1'] = 'weak'
    clone_node['password2'] = 'weak'
    data = (clone_node, 'Your password must contain at least four types which are an alphabet (uppercase/lowercase), a number, and a symbol.')
  elif request.param == 'invalid-screen-name-length':
    clone_node['screen_name'] = '1'*129
    data = (clone_node, 'Ensure this value has at most 128 character')

  return data

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_invalid_post_request_of_create_account_page(mocker, client, get_create_account_url, get_input_patterns_for_create_account_page):
  mocker.patch('account.forms.get_digest', return_value='hoge')
  params, err_msg = get_input_patterns_for_create_account_page
  url = get_create_account_url
  response = client.post(url, data=params)
  form = response.context['form']

  assert response.status_code == status.HTTP_200_OK
  assert err_msg in str(form.errors)

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_invalid_email_of_create_account_page(mocker, init_records, client, get_create_account_url):
  mocker.patch('account.forms.get_digest', return_value='hoge')
  email = init_records[0].email
  url = get_create_account_url
  params = {
    'email': email,
    'password1': 'hoge2@foo3Bar0',
    'password2': 'hoge2@foo3Bar0',
    'screen_name': 's-hoge',
    'hash_sign': 'hoge',
  }
  response = client.post(url, data=params)
  form = response.context['form']

  assert response.status_code == status.HTTP_200_OK
  assert 'User with this Email address already exists.' in str(form.errors)

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'default_email',
], [
  (None, ),
  ('hogehoge@example.com', ),
], ids=[
  'no-default-email-exists',
  'default-email-exists',
])
def test_valid_create_account_page(settings, mocker, client, get_create_account_url, default_email):
  mocker.patch('account.forms.get_digest', return_value='hoge')
  mocker.patch('account.models.EmailMessage.send', return_value=None)
  mail_mock = mocker.patch('account.models.EmailMessage.__init__', return_value=None)
  settings.DEFAULT_FROM_EMAIL = default_email
  url = get_create_account_url
  params = {
    'email': 'hogehoge@example.com',
    'password1': 'hoge2@foo3Bar0',
    'password2': 'hoge2@foo3Bar0',
    'screen_name': 's-hoge',
    'hash_sign': 'hoge',
  }
  response = client.post(url, data=params)
  args, kwargs = mail_mock.call_args
  subject = args[0]
  body = args[1]
  from_email = kwargs['from_email']
  to_email = kwargs['to']
  # Define expected from_email
  if default_email is None:
    callback = lambda email: email is None
  else:
    callback = lambda email: email == default_email

  assert response.status_code == status.HTTP_302_FOUND
  assert 'Quiz app - Account registration' in subject
  assert params['email'] in body
  assert 'account/complete-account-creation' in body
  assert callback(from_email)
  assert to_email == [params['email']]

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_invalid_access_by_authenticated_user_in_done_account_creation_page(init_records, client):
  user = init_records[0].user
  url = reverse('account:done_account_creation')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
def test_valid_access_in_done_account_creation_page(mocker, client):
  mocker.patch('account.views._get_timelimit_minutes', return_value=3)
  url = reverse('account:done_account_creation')
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK
  assert 'In addition, URL is valid for 3 minutes.' in response.context['warning_message']

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_invalid_access_by_authenticated_user_in_complete_account_creation_page(init_records, client):
  user = init_records[0].user
  url = reverse('account:complete_account_creation', kwargs={'token': 'hoge'})
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'mock_config',
  'http_status',
  'is_active',
], [
  ({'return_value': 'hoge'}, status.HTTP_200_OK, True),
  ({'side_effect': ValidationError('NG')}, status.HTTP_400_BAD_REQUEST, False),
], ids=[
  'valid-token',
  'invalid-token',
])
def test_valid_access_in_complete_account_creation_page(mocker, init_records, client, mock_config, http_status, is_active):
  someone = init_records[-1]
  user = UserModel.objects.create_user(email=someone.email, is_active=False)
  mocker.patch('account.validators.CustomRegistrationTokenValidator.validate', **mock_config)
  mocker.patch('account.validators.CustomRegistrationTokenValidator.get_instance', return_value=user)
  url = reverse('account:complete_account_creation', kwargs={'token': 'hoge'})
  response = client.get(url)
  target = UserModel.objects.get(pk=user.pk)

  assert response.status_code == http_status
  assert target.is_active == is_active

@pytest.mark.account
@pytest.mark.view
def test_without_authentication_for_change_password_page(client):
  url = reverse('account:update_password')
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_with_authentication_for_change_password_page(init_records, client):
  user = init_records[0].user
  url = reverse('account:update_password')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.fixture(params=[
  'invalid-old-password',
  'same-passwords',
  'invalid-new-password',
  'old-password-is-empty',
  'new-password1-is-empty',
  'new-password2-is-empty',
])
def get_input_patterns_for_change_password_page(request):
  original = {
    'old_password': 'a1H-2oG@3eF#',
    'new_password1': 'h2o!nH3@foo+',
    'new_password2': 'h2o!nH3@foo+',
  }
  clone_node = {key: val for key, val in original.items()}
  err_msg = 'This field is required.'

  if request.param == 'invalid-old-password':
    clone_node['old_password'] = 'a1H-2oG@xxx#'
    err_msg = 'Your old password was entered incorrectly. Please enter it again.'
  elif request.param == 'same-passwords':
    clone_node['old_password'] = clone_node['old_password']
    clone_node['new_password1'] = clone_node['old_password']
    err_msg = 'The old password is same as new password. Please enter difference passwords.'
  elif request.param == 'invalid-new-password':
    clone_node['new_password2'] = 'h2o!nH3@xxx+'
    err_msg = 'The two password fields didn’t match.'
  elif request.param == 'old-password-is-empty':
    del clone_node['old_password']
  elif request.param == 'new-password1-is-empty':
    del clone_node['new_password1']
  elif request.param == 'new-password2-is-empty':
    del clone_node['new_password2']

  return (clone_node, err_msg)

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_check_input_passwords_for_change_password_page(init_records, client, get_input_patterns_for_change_password_page):
  params, err_msg = get_input_patterns_for_change_password_page
  user = init_records[0].user
  url = reverse('account:update_password')
  client.force_login(user)
  response = client.post(url, data=params)
  form = response.context['form']

  assert response.status_code == status.HTTP_200_OK
  assert err_msg in str(form.errors)

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_valid_input_passwords_for_change_password_page(init_records, client):
  user = init_records[0].user
  url = reverse('account:update_password')
  params = {
    'old_password': 'a1H-2oG@3eF#',
    'new_password1': 'h2o!nH3@foo+',
    'new_password2': 'h2o!nH3@foo+',
  }
  client.force_login(user)
  response = client.post(url, data=params)

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == reverse('account:done_password_change')

@pytest.mark.account
@pytest.mark.view
def test_without_authentication_for_done_password_change_page(client):
  url = reverse('account:done_password_change')
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_with_authentication_for_done_password_change_page(init_records, client):
  user = init_records[0].user
  url = reverse('account:done_password_change')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.account
@pytest.mark.view
def test_without_authentication_for_reset_password_page(client):
  url = reverse('account:reset_password')
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_with_authentication_for_reset_password_page(init_records, client):
  user = init_records[0].user
  url = reverse('account:reset_password')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_invalid_email_in_reset_password_page(client):
  url = reverse('account:reset_password')
  params = {
    'email': '{}@ng.com'.format('1'*122),
  }
  response = client.post(url, data=params)
  form = response.context['form']

  assert response.status_code == status.HTTP_200_OK
  assert 'Ensure this value has at most 128 character' in str(form.errors)

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'user_idx',
], [
  (-2, ),
  (-1, ),
], ids=[
  'not-active-user',
  'user-does-not-exist',
])
def test_valid_of_not_active_user_in_reset_password_page(mocker, init_records, client, user_idx):
  email_mock = mocker.patch('django.contrib.auth.forms.EmailMultiAlternatives.send', return_value=None)
  url = reverse('account:reset_password')
  params = {
    'email': init_records[user_idx].email,
  }
  response = client.post(url, data=params)

  assert response.status_code == status.HTTP_302_FOUND
  assert email_mock.call_count == 0

@pytest.fixture
def get_url_of_confirm_page():
  from django.utils.encoding import force_bytes
  from django.utils.http import urlsafe_base64_encode
  from django.contrib.auth.tokens import default_token_generator

  def inner(user, is_GET=True):
    user_pk_bytes = force_bytes(UserModel._meta.pk.value_to_string(user))
    uid = urlsafe_base64_encode(user_pk_bytes)
    kwargs = {
      'uidb64': uid,
      'token': default_token_generator.make_token(user) if is_GET else 'set-password',
    }
    url = reverse('account:confirm_password_reset', kwargs=kwargs)

    return url

  return inner

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'port_num',
], [
  (':8426',),
  ('',),
], ids=[
  'set-port-number',
  'does-not-set-port-number',
])
def test_valid_email_in_reset_password_page(mocker, init_records, client, get_url_of_confirm_page, port_num):
  class FakeObj:
    def __init__(self):
      self.domain = 'foo'
  # Define test code
  fake_obj = FakeObj()
  mocker.patch('account.forms.get_current_site', return_value=fake_obj)
  mocker.patch('account.forms._get_forwarding_port', return_value=port_num)
  email_mock = mocker.patch('django.contrib.auth.forms.EmailMultiAlternatives.__init__', return_value=None)
  mocker.patch('django.contrib.auth.forms.EmailMultiAlternatives.send', return_value=None)
  email_addr = init_records[0].email
  user = init_records[0].user
  url = reverse('account:reset_password')
  params = {
    'email': email_addr,
  }
  response = client.post(url, data=params)
  args, _ = email_mock.call_args
  subject, body, _, to_email = args
  base_url = '/'.join(get_url_of_confirm_page(user).split('/')[:-1])
  exact_url = f'http://foo{port_num}{base_url}'

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == reverse('account:done_password_reset')
  assert 'Quiz app - Reset password' in subject
  assert exact_url in body
  assert 'The above url is valid for 5 minutes.' in body
  assert 'account/confirm-password-reset' in body
  assert to_email == [email_addr]

@pytest.mark.account
@pytest.mark.view
def test_without_authentication_for_done_password_reset_page(mocker, client):
  mocker.patch('account.views._get_password_reset_timeout_minutes', return_value=3)
  url = reverse('account:done_password_reset')
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK
  assert 'In addition, URL is valid for 3 minutes.' in response.context['warning_message']

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_with_authentication_for_done_password_reset_page(init_records, client):
  user = init_records[0].user
  url = reverse('account:done_password_reset')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'params',
  'err_msg',
], [
  ({'new_password1': 'h2o!nH3@foo+', 'new_password2': 'h2o!nH3@xxx+'}, 'The two password fields didn’t match.'),
  ({                                 'new_password2': 'h2o!nH3@foo+'}, 'This field is required.'),
  ({'new_password1': 'h2o!nH3@foo+'                                 }, 'This field is required.'),
], ids=[
  'invalid-new-password',
  'new-password1-is-empty',
  'new-password2-is-empty',
])
def test_invalid_passwords_for_confirm_password_reset_page(init_records, client, get_url_of_confirm_page, params, err_msg):
  user = init_records[0].user
  get_url = get_url_of_confirm_page(user)
  _ = client.get(get_url, follow=True)
  post_url = get_url_of_confirm_page(user, is_GET=False)
  response = client.post(post_url, data=params, follow=True)
  form = response.context['form']

  assert response.status_code == status.HTTP_200_OK
  assert err_msg in str(form.errors)

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_vald_password_for_confirm_password_reset_page(init_records, client, get_url_of_confirm_page):
  user = init_records[0].user
  get_url = get_url_of_confirm_page(user)
  _ = client.get(get_url, follow=True)
  # Post request
  params = {
    'new_password1': 'h2o!nH3@foo+',
    'new_password2': 'h2o!nH3@foo+',
  }
  post_url = get_url_of_confirm_page(user, is_GET=False)
  response = client.post(post_url, data=params, follow=True)
  success_url, _ = response.redirect_chain[0]

  assert response.status_code == status.HTTP_200_OK
  assert success_url == reverse('account:complete_password_reset')

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_with_authentication_for_confirm_password_reset_page(init_records, client):
  user = init_records[0].user
  url = reverse('account:confirm_password_reset', kwargs={'uidb64': 'hoge', 'token': 'foo'})
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
def test_without_authentication_for_complete_password_reset_page(client):
  url = reverse('account:complete_password_reset')
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_with_authentication_for_complete_password_reset_page(init_records, client):
  user = init_records[0].user
  url = reverse('account:complete_password_reset')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

# =============
# = User role =
# =============
@pytest.mark.account
@pytest.mark.view
def test_without_authentication_for_role_change_request_list_page(client):
  url = reverse('account:role_change_requests')
  response = client.get(url)
  redirected_url = '{}?next={}'.format(reverse('account:login'), url)

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == redirected_url

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'user_id',
], [
  (0, ),
  (1, ),
], ids=[
  'is-guest',
  'is-creator',
])
def test_invalid_role_for_role_change_request_list_page(init_records, client, user_id):
  user = init_records[user_id].user
  url = reverse('account:role_change_requests')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_with_authentication_valid_role_for_role_change_request_list_page(init_records, client):
  user = init_records[2].user
  url = reverse('account:role_change_requests')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.account
@pytest.mark.view
def test_without_authentication_for_create_role_change_request_page(client):
  url = reverse('account:create_role_change_request')
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'user_id',
], [
  (1, ),
  (2, ),
], ids=[
  'is-creator',
  'is-manager',
])
def test_invalid_role_for_create_role_change_request_page(init_records, client, user_id):
  user = init_records[user_id].user
  url = reverse('account:create_role_change_request')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'is_completed',
], [
  (True, ),
  (False, ),
], ids=[
  'is-completed',
  'is-not-completed',
])
def test_record_has_already_existed_for_create_role_change_request_page(init_records, client, is_completed):
  user = init_records[0].user
  _ = factories.RoleApprovalFactory(user=user, is_completed=is_completed)
  url = reverse('account:create_role_change_request')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_valid_get_request_for_create_role_change_request_page(init_records, client):
  user = init_records[0].user
  url = reverse('account:create_role_change_request')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_valid_post_request_for_create_role_change_request_page(init_records, client):
  user = init_records[0].user
  url = reverse('account:create_role_change_request')
  success_url = reverse('account:user_profile')
  client.force_login(user)
  response = client.post(url)
  count = user.approvals.all().count()

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == success_url
  assert count == 1

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_cannot_access_of_get_method_for_update_role_approval(init_records, client):
  guest = init_records[0].user
  user = init_records[2].user
  target = factories.RoleApprovalFactory(user=guest)
  url = reverse('account:update_role_approval', kwargs={'pk': target.pk})
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'is_approve',
], [
  (True, ),
  (False, ),
], ids=[
  'is-approve',
  'is-not-approve',
])
def test_without_authentication_for_update_role_approval(init_records, client, is_approve):
  guest = init_records[0].user
  target = factories.RoleApprovalFactory(user=guest)
  url = reverse('account:update_role_approval', kwargs={'pk': target.pk})
  params = {
    'is_approve': is_approve
  }
  response = client.post(url, data=params)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'user_idx',
], [
  (0, ),
  (1, ),
], ids=[
  'is-guest',
  'is-creator',
])
def test_invalid_role_for_update_role_approval(init_records, client, user_idx):
  guest = init_records[0].user
  user = init_records[user_idx].user
  target = factories.RoleApprovalFactory(user=guest)
  url = reverse('account:update_role_approval', kwargs={'pk': target.pk})
  params = {
    'is_approve': True
  }
  client.force_login(user)
  response = client.post(url, data=params)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_is_approve_for_update_role_approval(init_records, client):
  guest = init_records[0].user
  manager = init_records[2].user
  target = factories.RoleApprovalFactory(user=guest)
  url = reverse('account:update_role_approval', kwargs={'pk': target.pk})
  params = {
    'is_approve': True
  }
  client.force_login(manager)
  response = client.post(url, data=params)
  user = UserModel.objects.get(pk=guest.pk)
  instance = models.RoleApproval.objects.get(pk=target.pk)

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == reverse('account:role_change_requests')
  assert user.role == models.RoleType.CREATOR
  assert instance.is_completed

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_is_not_approve_for_update_role_approval(init_records, client):
  guest = init_records[0].user
  manager = init_records[2].user
  target = factories.RoleApprovalFactory(user=guest)
  url = reverse('account:update_role_approval', kwargs={'pk': target.pk})
  params = {
    'is_approve': False
  }
  client.force_login(manager)
  response = client.post(url, data=params)
  user = UserModel.objects.get(pk=guest.pk)
  count = models.RoleApproval.objects.all().count()

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == reverse('account:role_change_requests')
  assert user.role == models.RoleType.GUEST
  assert count == 0

# ===========
# = Friends =
# ===========
@pytest.fixture(params=['is-superuser', 'is-staff', 'is-manager', 'is-creator', 'is-guest'])
def get_specific_users(django_db_blocker, request):
  key = request.param
  configs = {
    'is-superuser': {'is_staff': True, 'is_superuser': True, 'role': models.RoleType.GUEST},
    'is-staff': {'is_staff': True, 'is_superuser': False, 'role': models.RoleType.GUEST},
    'is-manager': {'is_staff': False, 'is_superuser': False, 'role': models.RoleType.MANAGER},
    'is-creator': {'is_staff': False, 'is_superuser': False, 'role': models.RoleType.CREATOR},
    'is-guest': {'is_staff': False, 'is_superuser': False, 'role': models.RoleType.GUEST},
  }
  with django_db_blocker.unblock():
    kwargs = configs[key]
    user = factories.UserFactory(is_active=True, **kwargs)

  return key, user

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_without_authentication_for_update_friend_page(init_records, client):
  url = reverse('account:update_friend')
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_with_authentication_for_update_friend_page(get_specific_users, client):
  codes = {
    'is-superuser': status.HTTP_403_FORBIDDEN,
    'is-staff': status.HTTP_200_OK,
    'is-manager': status.HTTP_403_FORBIDDEN,
    'is-creator': status.HTTP_200_OK,
    'is-guest': status.HTTP_200_OK,
  }
  key, user = get_specific_users
  status_code = codes[key]
  url = reverse('account:update_friend')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status_code

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'number_of_members',
], [
  (0, ),
  (1, ),
  (2, ),
], ids=[
  'no-members',
  'only-one-member',
  'many-members',
])
def test_valid_access_in_update_friend_page(client, number_of_members):
  _ = factories.UserFactory(is_active=True, is_staff=True, is_superuser=True)
  _ = factories.UserFactory(is_active=True, is_staff=True)
  _ = factories.UserFactory(is_active=False, is_staff=False)
  candidates = list(factories.UserFactory.create_batch(number_of_members, is_active=True)) if number_of_members > 0 else []
  user = factories.UserFactory(is_active=True)
  url = reverse('account:update_friend')
  client.force_login(user)
  params = {
    'friends': [str(item.pk) for item in candidates],
  }
  response = client.post(url, data=params)
  updated_user = UserModel.objects.get(pk=user.pk)

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == reverse('account:user_profile')
  assert updated_user.friends.all().count() == number_of_members

# ====================
# = Individual group =
# ====================
@pytest.mark.account
@pytest.mark.view
def test_without_authentication_for_individual_group_list_page(client):
  url = reverse('account:individual_group_list')
  response = client.get(url)
  redirected_url = '{}?next={}'.format(reverse('account:login'), url)

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == redirected_url

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_with_authentication_for_individual_group_list_page(get_specific_users, client):
  codes = {
    'is-superuser': status.HTTP_403_FORBIDDEN,
    'is-staff': status.HTTP_200_OK,
    'is-manager': status.HTTP_403_FORBIDDEN,
    'is-creator': status.HTTP_200_OK,
    'is-guest': status.HTTP_200_OK,
  }
  key, user = get_specific_users
  status_code = codes[key]
  url = reverse('account:individual_group_list')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status_code

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'number_of_groups',
  'name',
], [
  (0, 'test-group0'),
  (1, 'test-group1'),
  (2, 'test-group2'),
], ids=[
  'no-groups',
  'only-one-group',
  'many-groups',
])
def test_check_groups_in_individual_group_list_page(client, number_of_groups, name):
  _ = factories.UserFactory(is_active=True, is_staff=True, is_superuser=True)
  _ = factories.UserFactory(is_active=True, is_staff=True)
  friends = list(factories.UserFactory.create_batch(5, is_active=True))
  user = factories.UserFactory(is_active=True, friends=friends)
  groups = factories.IndividualGroupFactory.create_batch(number_of_groups, owner=user, name=name, members=[friends[0], friends[2]])
  # Get access
  url = reverse('account:individual_group_list')
  client.force_login(user)
  response = client.get(url)
  lists = response.context['own_groups']

  assert response.status_code == status.HTTP_200_OK
  assert len(lists) == number_of_groups

@pytest.mark.account
@pytest.mark.view
def test_without_authentication_for_create_individual_group_page(client):
  url = reverse('account:create_group')
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_with_authentication_for_create_individual_group_page(get_specific_users, client):
  codes = {
    'is-superuser': status.HTTP_403_FORBIDDEN,
    'is-staff': status.HTTP_200_OK,
    'is-manager': status.HTTP_403_FORBIDDEN,
    'is-creator': status.HTTP_200_OK,
    'is-guest': status.HTTP_200_OK,
  }
  key, user = get_specific_users
  status_code = codes[key]
  url = reverse('account:create_group')
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status_code

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'name',
  'number_of_request_members',
], [
  ('group1', 1),
  ('group2', 2),
], ids=[
  'only-one-member',
  'many-members',
])
def test_valid_request_for_create_individual_group_page(client, name, number_of_request_members):
  friends = list(factories.UserFactory.create_batch(3, is_active=True))
  user = factories.UserFactory(is_active=True, friends=friends)
  url = reverse('account:create_group')
  params = {
    'name': name,
    'members': [str(friends[idx].pk) for idx in range(number_of_request_members)],
  }
  client.force_login(user)
  response = client.post(url, data=params)
  success_url = reverse('account:individual_group_list')
  _res = client.get(success_url)
  groups = _res.context['own_groups']

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == success_url
  assert len(groups) == 1
  assert groups[0].members.all().count() == number_of_request_members

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_without_authentication_for_update_individual_group_page(init_records, client):
  user = init_records[0].user
  instance = factories.IndividualGroupFactory(owner=user)
  url = reverse('account:update_group', kwargs={'pk': instance.pk})
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_with_authentication_for_update_individual_group_page(init_records, get_specific_users, client):
  codes = {
    'is-superuser': status.HTTP_403_FORBIDDEN,
    'is-staff': status.HTTP_403_FORBIDDEN,
    'is-manager': status.HTTP_403_FORBIDDEN,
    'is-creator': status.HTTP_403_FORBIDDEN,
    'is-guest': status.HTTP_200_OK, # Assumption: the target is owner
  }
  key, user = get_specific_users
  status_code = codes[key]
  owner = user if key == 'is-guest' else init_records[0].user
  instance = factories.IndividualGroupFactory(owner=owner)
  url = reverse('account:update_group', kwargs={'pk': instance.pk})
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status_code

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_invalid_access_for_update_individual_group_page(init_records, client):
  owner = init_records[0].user
  other = init_records[1].user
  instance = factories.IndividualGroupFactory(owner=owner)
  url = reverse('account:update_group', kwargs={'pk': instance.pk})
  client.force_login(other)
  response = client.get(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'old_member_indices',
  'new_member_indices',
], [
  ([0], [1]),
  ([0], [0, 1]),
  ([0], [1, 2]),
], ids=[
  'same-count',
  'add-member',
  'add-other-members',
])
def test_update_record_for_update_individual_group_page(client, old_member_indices, new_member_indices):
  friends = list(factories.UserFactory.create_batch(5, is_active=True))
  user = factories.UserFactory(is_active=True, friends=friends)
  instance = factories.IndividualGroupFactory(owner=user, members=[friends[idx] for idx in old_member_indices])
  new_members = [friends[idx] for idx in new_member_indices]
  params = {
    'name': instance.name,
    'members': [str(item.pk) for item in new_members],
  }
  url = reverse('account:update_group', kwargs={'pk': instance.pk})
  client.force_login(user)
  response = client.post(url, data=params)
  success_url = reverse('account:individual_group_list')
  _instance = models.IndividualGroup.objects.get(pk=instance.pk)
  updated_members = list(_instance.members.all())
  _sort_record = lambda records: sorted(records, key=lambda item: str(item.pk))

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == success_url
  assert all([
    str(estimated.pk) == str(exact.pk)
    for estimated, exact in zip(_sort_record(updated_members), _sort_record(new_members))
  ])

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_invalid_get_access_for_delete_individual_group(client):
  friends = list(factories.UserFactory.create_batch(2, is_active=True))
  user = factories.UserFactory(is_active=True, friends=friends)
  instance = factories.IndividualGroupFactory(owner=user, members=[friends[0]])
  url = reverse('account:delete_group', kwargs={'pk': instance.pk})
  client.force_login(user)
  response = client.get(url)

  assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_without_authentication_for_delete_individual_group(client):
  friends = list(factories.UserFactory.create_batch(2, is_active=True))
  user = factories.UserFactory(is_active=True, friends=friends)
  instance = factories.IndividualGroupFactory(owner=user, members=[friends[0]])
  url = reverse('account:delete_group', kwargs={'pk': instance.pk})
  response = client.post(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_invalid_access_by_other_user_for_delete_individual_group(client):
  friends = list(factories.UserFactory.create_batch(2, is_active=True))
  user = factories.UserFactory(is_active=True, friends=friends)
  other = factories.UserFactory(is_active=True)
  instance = factories.IndividualGroupFactory(owner=user, members=[friends[0]])
  url = reverse('account:delete_group', kwargs={'pk': instance.pk})
  client.force_login(other)
  response = client.post(url)

  assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_delete_record_in_delete_individual_group(client):
  friends = list(factories.UserFactory.create_batch(2, is_active=True))
  user = factories.UserFactory(is_active=True, friends=friends)
  instance = factories.IndividualGroupFactory(owner=user, members=[friends[0]])
  url = reverse('account:delete_group', kwargs={'pk': instance.pk})
  success_url = reverse('account:individual_group_list')
  client.force_login(user)
  response = client.post(url)
  count = models.IndividualGroup.objects.all().count()

  assert response.status_code == status.HTTP_302_FOUND
  assert response['Location'] == success_url
  assert count == 0

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'is_authenticated',
  'config',
  'status_code',
], [
  (True, {'role': models.RoleType.GUEST, 'is_staff': True, 'is_superuser': True}, status.HTTP_403_FORBIDDEN),
  (True, {'role': models.RoleType.MANAGER}, status.HTTP_403_FORBIDDEN),
  (True, {'role': models.RoleType.CREATOR}, status.HTTP_405_METHOD_NOT_ALLOWED),
  (True, {'role': models.RoleType.GUEST}, status.HTTP_405_METHOD_NOT_ALLOWED),
  (False, None, status.HTTP_403_FORBIDDEN),
], ids=[
  'superuser-who-is-authenticated',
  'manager-who-is-authenticated',
  'creator-who-is-authenticated',
  'guest-who-is-authenticated',
  'is-anonymous-user',
])
def test_get_access_to_individual_group_ajax_response(client, is_authenticated, config, status_code):
  url = reverse('account:ajax_get_options')
  # Execute force login or not
  if is_authenticated:
    user = factories.UserFactory(is_active=True, **config)
    client.force_login(user)
  response = client.get(url)

  assert response.status_code == status_code

@pytest.fixture(params=['is-guest', 'is-creator'])
def get_players_with_friends(request):
  friends = list(factories.UserFactory.create_batch(4, is_active=True))

  if request.param == 'is-guest':
    user = factories.UserFactory(is_active=True, friends=friends, role=models.RoleType.GUEST)
  else:
    user = factories.UserFactory(is_active=True, friends=friends, role=models.RoleType.CREATOR)

  return user, friends

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize([
  'arg_type',
  'expected_type',
], [
  ('only-group', 'specific'),
  ('no-data', 'all'),
], ids=lambda xs: str(xs))
def test_post_access_to_individual_group_ajax_response(get_players_with_friends, rf, arg_type, expected_type):
  user, friends = get_players_with_friends
  group = factories.IndividualGroupFactory(owner=user, members=[friends[0], friends[-1]])
  patterns = {
    'only-group': {'group_pk': str(group.pk)},
    'no-data':    {},
  }
  expected = {
    'specific': g_generate_item([friends[0], friends[-1]], False),
    'all': g_generate_item(UserModel.objects.collect_valid_normal_users(), False),
  }
  # Get option data
  url = reverse('account:ajax_get_options')
  params = patterns[arg_type]
  exact_arr = expected[expected_type]
  # Execute req-res
  request = rf.post(url, data=params, content_type='application/json')
  request.user = user
  ajax_view = views.IndividualGroupAjaxResponse.as_view()
  response = ajax_view(request)
  data = json.loads(response.content)
  options = data['options']

  assert response.status_code == status.HTTP_200_OK
  assert len(options) == len(exact_arr)
  assert g_compare_options(options, exact_arr)

@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
def test_invalid_request_to_individual_group_ajax_response(client):
  friends = list(factories.UserFactory.create_batch(4, is_active=True))
  user = factories.UserFactory(is_active=True, friends=friends)
  url = reverse('account:ajax_get_options')
  params = {'group_pk': 123}
  # Execute req-res
  client.force_login(user)
  response = client.post(url, data=params, headers={'Content-Type': 'application/json'})
  data = json.loads(response.content)
  options = data['options']

  assert response.status_code == status.HTTP_200_OK
  assert len(options) == 0