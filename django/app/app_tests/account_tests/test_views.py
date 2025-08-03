import pytest
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
import urllib.parse

UserModel = get_user_model()

@pytest.fixture(scope='module')
def get_guest(django_db_blocker):
  with django_db_blocker.unblock():
    email = 'hoge@guest.com'
    password = 'a1H-2oG@3eF#'
    user = UserModel.objects.create_user(is_active=True, email=email, password=password, role=models.RoleType.GUEST)

  return user, email, password

@pytest.fixture(scope='module')
def get_creator(django_db_blocker):
  with django_db_blocker.unblock():
    email = 'foo@creator.com'
    password = 'h2o!nH3@foo+'
    user = UserModel.objects.create_user(is_active=True, email=email, password=password, role=models.RoleType.CREATOR)

  return user, email, password

@pytest.fixture(scope='module')
def get_manager(django_db_blocker):
  with django_db_blocker.unblock():
    email = 'bar@manager.com'
    password = 'So4@Easy3+Mngr'
    user = UserModel.objects.create_user(is_active=True, email=email, password=password, role=models.RoleType.MANAGER)

  return user, email, password

@pytest.fixture(scope='module')
def get_inactive_user(django_db_blocker):
  with django_db_blocker.unblock():
    email = 'inactive@none.com'
    password = 'cann0t-use-this-Account'
    user = UserModel.objects.create_user(email=email, password=password)

  return user, email, password

@pytest.fixture(scope='module')
def get_invalid_account():
  return None, 'someone@none.com', 'nobody+knows-No.0x02'

@pytest.fixture(scope='module')
def get_superuser(django_db_blocker):
  with django_db_blocker.unblock():
    email = 'superuser@example.com'
    password = 'this-Acc0unt-is-superuser'
    kwargs = {
      'screen_name': 'test-admin',
      'is_staff': True,
      'is_superuser': True,
    }
    user = UserModel.objects.create_superuser(is_active=True, email=email, password=password, **kwargs)

  return user, email, password

@pytest.fixture(params=['in-active-user', 'invalid-account'], scope='module')
def get_invalid_users(get_inactive_user, get_invalid_account, request):
  if request.param == 'in-active-user':
    _, email, _ = get_inactive_user
  else:
    _, email, _ = get_invalid_account

  return email

@pytest.fixture(params=['is-manager', 'is-creator'], scope='module')
def get_creator_manager(request, get_manager, get_creator):
  if request.param == 'is-manager':
    user, _, _ = get_manager
  else:
    user, _, _ = get_creator

  return user

@pytest.fixture(params=['is-creator', 'is-guest'], scope='module')
def get_players(request, get_guest, get_creator):
  key = request.param
  configs = {
    'is-creator': tuple(get_creator),
    'is-guest': tuple(get_guest),
  }
  user = configs[key][0]

  return key, user

@pytest.fixture(params=['superuser', 'manager'], scope='module')
def get_has_manager_role_members(request, get_superuser, get_manager):
  if request.param == 'superuser':
    user, _, _ = get_superuser
  else:
    user, _, _ = get_manager

  return user

@pytest.fixture(params=['is-superuser', 'is-manager', 'is-creator', 'is-guest'], scope='module')
def get_specific_users(request, get_guest, get_creator, get_manager, get_superuser):
  key = request.param
  configs = {
    'is-superuser': tuple(get_superuser),
    'is-manager': tuple(get_manager),
    'is-creator': tuple(get_creator),
    'is-guest': tuple(get_guest),
  }
  user = configs[key][0]

  return key, user

class Common:
  # Index/Login/Logout
  index_url = reverse('utils:index')
  login_url = reverse('account:login')
  logout_url = reverse('account:logout')
  # User profile
  user_profile_url = reverse('account:user_profile')
  update_profile_url = reverse('account:update_profile')
  # Create account
  create_account_url = reverse('account:create_account')
  done_account_creation_url = reverse('account:done_account_creation')
  complete_account_creation_url = reverse('account:complete_account_creation', kwargs={'token': 'hoge'})
  # Change password
  update_password_url = reverse('account:update_password')
  done_password_change_url = reverse('account:done_password_change')
  # Reset password
  reset_password_url = reverse('account:reset_password')
  done_password_reset_url = reverse('account:done_password_reset')
  complete_password_reset_url = reverse('account:complete_password_reset')
  # Change role
  role_change_requests_url = reverse('account:role_change_requests')
  create_role_change_request_url = reverse('account:create_role_change_request')
  update_role_approval_url = lambda _self, pk: reverse('account:update_role_approval', kwargs={'pk': pk})
  # Add friend
  update_friend_url = reverse('account:update_friend')
  # Individual group
  individual_group_list_url = reverse('account:individual_group_list')
  create_group_url = reverse('account:create_group')
  update_group_url = lambda _self, pk: reverse('account:update_group', kwargs={'pk': pk})
  delete_group_url = lambda _self, pk: reverse('account:delete_group', kwargs={'pk': pk})
  # Ajax
  ajax_get_options_url = reverse('account:ajax_get_options')
  # Download creator
  download_creator_url = reverse('account:download_creator')

# ====================
# = Global functions =
# ====================
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

# ======================
# = Index/Login/Logout =
# ======================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestIndexLoginLogout(Common):
  def test_index_view_get_access(self, client):
    response = client.get(reverse('account:alternative'))

    assert response.status_code == status.HTTP_200_OK

  def test_login_view_get_access(self, client):
    response = client.get(self.login_url)

    assert response.status_code == status.HTTP_200_OK

  def test_login_view_post_access(self, get_guest, client):
    _, email, password = get_guest
    params = {
      'email': email,
      'password': password,
    }
    response = client.post(self.login_url, params)

    assert response.status_code == status.HTTP_200_OK

  def test_logout_page(self, get_guest, client):
    user, _, _ = get_guest
    client.force_login(user)
    response = client.post(self.logout_url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.index_url

# ============================
# = Show/Update user profile =
# ============================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestUserProfilePage(Common):
  def test_with_authentication(self, get_guest, client):
    user, _, _ = get_guest
    client.force_login(user)
    response = client.get(self.user_profile_url)

    assert response.status_code == status.HTTP_200_OK

  def test_without_authentication(self, client):
    response = client.get(self.user_profile_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_access_to_update_user_profile_page(self, get_guest, client):
    user, _, _ = get_guest
    client.force_login(user)
    response = client.get(self.update_profile_url)

    assert response.status_code == status.HTTP_200_OK

  def test_update_user_profile(self, client):
    user = factories.UserFactory(is_active=True, screen_name='old-name')
    new_name = 'new-name'
    client.force_login(user)
    response = client.post(self.update_profile_url, data={'screen_name': new_name})
    modified_user = UserModel.objects.get(pk=user.pk)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.user_profile_url
    assert modified_user.screen_name == new_name

# =====================
# = CreateAccountPage =
# =====================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestCreateAccountPage(Common):
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
  def test_invalid_access_of_create_account_page(self, get_guest, client, http_method, args):
    funcs = {
      'get': lambda url, params: client.get(url),
      'post': lambda url, params: client.post(url, data=params),
    }
    user, _, _ = get_guest
    # Force login
    client.force_login(user)
    caller = funcs[http_method]
    response = caller(self.create_account_url, args)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_get_access_of_create_account_page(self, client):
    response = client.get(self.create_account_url)

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
  def get_invalid_patterns(self, request):
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

  def test_invalid_post_request(self, mocker, client, get_invalid_patterns):
    mocker.patch('account.forms.get_digest', return_value='hoge')
    params, err_msg = get_invalid_patterns
    response = client.post(self.create_account_url, data=params)
    form = response.context['form']

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(form.errors)

  def test_invalid_email(self, mocker, get_guest, client):
    mocker.patch('account.forms.get_digest', return_value='hoge')
    _, email, _ = get_guest
    params = {
      'email': email,
      'password1': 'hoge2@foo3Bar0',
      'password2': 'hoge2@foo3Bar0',
      'screen_name': 's-hoge',
      'hash_sign': 'hoge',
    }
    response = client.post(self.create_account_url, data=params)
    form = response.context['form']

    assert response.status_code == status.HTTP_200_OK
    assert 'User with this Email address already exists.' in str(form.errors)

  @pytest.mark.parametrize([
    'default_email',
  ], [
    (None, ),
    ('hogehoge@example.com', ),
  ], ids=[
    'no-default-email-exists',
    'default-email-exists',
  ])
  def test_valid_create_account_page(self, settings, mocker, client, default_email):
    mocker.patch('account.forms.get_digest', return_value='hoge')
    mocker.patch('account.models.EmailMessage.send', return_value=None)
    mail_mock = mocker.patch('account.models.EmailMessage.__init__', return_value=None)
    settings.DEFAULT_FROM_EMAIL = default_email
    params = {
      'email': 'hogehoge@example.com',
      'password1': 'hoge2@foo3Bar0',
      'password2': 'hoge2@foo3Bar0',
      'screen_name': 's-hoge',
      'hash_sign': 'hoge',
    }
    response = client.post(self.create_account_url, data=params)
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

# =====================
# = CreateAccountPage =
# =====================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestDoneAccountCreationPage(Common):
  def test_invalid_access_by_authenticated_user(self, get_guest, client):
    user, _, _ = get_guest
    client.force_login(user)
    response = client.get(self.done_account_creation_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_access(self, mocker, client):
    mocker.patch('account.views._get_timelimit_minutes', return_value=3)
    response = client.get(self.done_account_creation_url)

    assert response.status_code == status.HTTP_200_OK
    assert 'In addition, URL is valid for 3 minutes.' in response.context['warning_message']

# ===============================
# = CompleteAccountCreationPage =
# ===============================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestCompleteAccountCreationPage(Common):
  def test_invalid_access_by_authenticated_user(self, get_guest, client):
    user, _, _ = get_guest
    client.force_login(user)
    response = client.get(self.complete_account_creation_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

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
  def test_valid_access(self, mocker, get_invalid_account, client, mock_config, http_status, is_active):
    _, email, _ = get_invalid_account
    user = UserModel.objects.create_user(email=email, is_active=False)
    mocker.patch('account.validators.CustomRegistrationTokenValidator.validate', **mock_config)
    mocker.patch('account.validators.CustomRegistrationTokenValidator.get_instance', return_value=user)
    response = client.get(self.complete_account_creation_url)
    target = UserModel.objects.get(pk=user.pk)

    assert response.status_code == http_status
    assert target.is_active == is_active

# ======================
# = ChangePasswordPage =
# ======================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestChangePasswordPage(Common):
  def test_without_authentication(self, client):
    response = client.get(self.update_password_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_with_authentication(self, get_guest, client):
    user, _, _ = get_guest
    client.force_login(user)
    response = client.get(self.update_password_url)

    assert response.status_code == status.HTTP_200_OK

  @pytest.fixture(params=[
    'invalid-old-password',
    'same-passwords',
    'invalid-new-password',
    'old-password-is-empty',
    'new-password1-is-empty',
    'new-password2-is-empty',
  ])
  def get_invalid_patterns(self, request):
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

  def test_check_input_passwords(self, get_guest, client, get_invalid_patterns):
    params, err_msg = get_invalid_patterns
    user, _, _ = get_guest
    client.force_login(user)
    response = client.post(self.update_password_url, data=params)
    form = response.context['form']

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(form.errors)

  def test_valid_input_passwords(self, client):
    user = factories.UserFactory(is_active=True)
    user.set_password('a1H-2oG@3eF#')
    user.save()
    params = {
      'old_password': 'a1H-2oG@3eF#',
      'new_password1': 'h2o!nH3@foo+',
      'new_password2': 'h2o!nH3@foo+',
    }
    client.force_login(user)
    response = client.post(self.update_password_url, data=params)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.done_password_change_url

# ==========================
# = DonePasswordChangePage =
# ==========================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestDonePasswordChangePage(Common):
  def test_without_authentication(self, client):
    response = client.get(self.done_password_change_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_with_authentication(self, get_guest, client):
    user, _, _ = get_guest
    client.force_login(user)
    response = client.get(self.done_password_change_url)

    assert response.status_code == status.HTTP_200_OK

# =====================
# = ResetPasswordView =
# =====================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestResetPasswordView(Common):
  def test_reset_password_page_without_authentication(self, client):
    response = client.get(self.reset_password_url)

    assert response.status_code == status.HTTP_200_OK

  def test_reset_password_page_with_authentication(self, get_guest, client):
    user, _, _ = get_guest
    client.force_login(user)
    response = client.get(self.reset_password_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_invalid_email(self, client):
    params = {
      'email': '{}@ng.com'.format('1'*122),
    }
    response = client.post(self.reset_password_url, data=params)
    form = response.context['form']

    assert response.status_code == status.HTTP_200_OK
    assert 'Ensure this value has at most 128 character' in str(form.errors)

  def test_check_not_active_user(self, mocker, get_invalid_users, client):
    email_mock = mocker.patch('django.contrib.auth.forms.EmailMultiAlternatives.send', return_value=None)
    params = {
      'email': get_invalid_users,
    }
    response = client.post(self.reset_password_url, data=params)
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert 'The given email address is not registered or not enabled. Please check your email address.' in str(errors)
    assert email_mock.call_count == 0

  @pytest.fixture
  def confirm_page_url(self):
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

  @pytest.mark.parametrize([
    'port_num',
  ], [
    (':8426',),
    ('',),
  ], ids=[
    'set-port-number',
    'does-not-set-port-number',
  ])
  def test_valid_email(self, mocker, get_guest, client, confirm_page_url, port_num):
    class FakeObj:
      domain = 'foo'
    # Define test code
    fake_obj = FakeObj()
    mocker.patch('account.forms.get_current_site', return_value=fake_obj)
    mocker.patch('account.forms._get_forwarding_port', return_value=port_num)
    email_mock = mocker.patch('django.contrib.auth.forms.EmailMultiAlternatives.__init__', return_value=None)
    mocker.patch('django.contrib.auth.forms.EmailMultiAlternatives.send', return_value=None)
    user, email_addr, _ = get_guest
    params = {
      'email': email_addr,
    }
    response = client.post(self.reset_password_url, data=params)
    args, _ = email_mock.call_args
    subject, body, _, to_email = args
    base_url = '/'.join(confirm_page_url(user).split('/')[:-1])
    exact_url = f'http://foo{port_num}{base_url}'

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.done_password_reset_url
    assert 'Quiz app - Reset password' in subject
    assert exact_url in body
    assert 'The above url is valid for 5 minutes.' in body
    assert 'account/confirm-password-reset' in body
    assert to_email == [email_addr]

  def test_done_password_reset_page_without_authentication(self, mocker, client):
    mocker.patch('account.views._get_password_reset_timeout_minutes', return_value=3)
    response = client.get(self.done_password_reset_url)

    assert response.status_code == status.HTTP_200_OK
    assert 'In addition, URL is valid for 3 minutes.' in response.context['warning_message']

  def test_done_password_reset_page_with_authentication(self, get_guest, client):
    user, _, _ = get_guest
    client.force_login(user)
    response = client.get(self.done_password_reset_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

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
  def test_invalid_passwords(self, client, confirm_page_url, params, err_msg):
    passowrd = 'h2o!MnO2@abc+'
    user = factories.UserFactory(is_active=True)
    user.set_password(passowrd)
    user.save()
    get_url = confirm_page_url(user)
    _ = client.get(get_url, follow=True)
    post_url = confirm_page_url(user, is_GET=False)
    response = client.post(post_url, data=params, follow=True)
    form = response.context['form']

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(form.errors)

  def test_vald_password(self, client, confirm_page_url):
    user = factories.UserFactory(is_active=True)
    get_url = confirm_page_url(user)
    _ = client.get(get_url, follow=True)
    # Post request
    params = {
      'new_password1': 'h2o!nH3@foo+',
      'new_password2': 'h2o!nH3@foo+',
    }
    post_url = confirm_page_url(user, is_GET=False)
    response = client.post(post_url, data=params, follow=True)
    success_url, _ = response.redirect_chain[0]

    assert response.status_code == status.HTTP_200_OK
    assert success_url == self.complete_password_reset_url

  def test_confirm_password_reset_page_with_authentication(self, get_guest, client):
    user, _, _ = get_guest
    url = reverse('account:confirm_password_reset', kwargs={'uidb64': 'hoge', 'token': 'foo'})
    client.force_login(user)
    response = client.get(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_confirm_password_reset_page_with_invalid_token(self, client):
    url = reverse('account:confirm_password_reset', kwargs={'uidb64': 'hoge', 'token': 'foo'})
    response = client.get(url)

    assert response.status_code == status.HTTP_400_BAD_REQUEST

  def test_complete_password_reset_page_without_authentication(self, client):
    response = client.get(self.complete_password_reset_url)

    assert response.status_code == status.HTTP_200_OK

  def test_complete_password_reset_page_with_authentication(self, get_guest, client):
    user, _, _ = get_guest
    client.force_login(user)
    response = client.get(self.complete_password_reset_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

# =============================
# = RoleChangeRequestListPage =
# =============================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestRoleChangeRequestListPage(Common):
  def test_without_authentication(self, client):
    response = client.get(self.role_change_requests_url)
    redirected_url = '{}?next={}'.format(self.login_url, self.role_change_requests_url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == redirected_url

  def test_invalid_role(self, get_players, client):
    _, user = get_players
    client.force_login(user)
    response = client.get(self.role_change_requests_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_role_with_authentication(self, get_manager, client):
    user, _, _ = get_manager
    client.force_login(user)
    response = client.get(self.role_change_requests_url)

    assert response.status_code == status.HTTP_200_OK

# ===============================
# = CreateRoleChangeRequestPage =
# ===============================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestCreateRoleChangeRequestPage(Common):
  def test_without_authentication(self, client):
    response = client.get(self.create_role_change_request_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_invalid_role(self, get_creator_manager, client):
    user = get_creator_manager
    client.force_login(user)
    response = client.get(self.create_role_change_request_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  @pytest.mark.parametrize([
    'is_completed',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'is-completed',
    'is-not-completed',
  ])
  def test_record_has_already_existed(self, get_guest, client, is_completed):
    user, _, _ = get_guest
    _ = factories.RoleApprovalFactory(user=user, is_completed=is_completed)
    client.force_login(user)
    response = client.get(self.create_role_change_request_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_valid_get_request(self, get_guest, client):
    user, _, _ = get_guest
    client.force_login(user)
    response = client.get(self.create_role_change_request_url)

    assert response.status_code == status.HTTP_200_OK

  def test_valid_post_request(self, get_guest, client):
    user, _, _ = get_guest
    client.force_login(user)
    response = client.post(self.create_role_change_request_url)
    count = user.approvals.count()

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.user_profile_url
    assert count == 1

# ======================
# = UpdateRoleApproval =
# ======================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestUpdateRoleApproval(Common):
  def test_cannot_access_of_get_method(self, get_guest, get_manager, client):
    guest, _, _ = get_guest
    user, _, _ = get_manager
    target = factories.RoleApprovalFactory(user=guest)
    client.force_login(user)
    response = client.get(self.update_role_approval_url(target.pk))

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

  @pytest.mark.parametrize([
    'is_approve',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'is-approve',
    'is-not-approve',
  ])
  def test_without_authentication(self, get_guest, client, is_approve):
    guest, _, _ = get_guest
    target = factories.RoleApprovalFactory(user=guest)
    params = {
      'is_approve': is_approve
    }
    response = client.post(self.update_role_approval_url(target.pk), data=params)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_invalid_role(self, get_guest, get_players, client):
    guest, _, _ = get_guest
    _, user = get_players
    target = factories.RoleApprovalFactory(user=guest)
    params = {
      'is_approve': True
    }
    client.force_login(user)
    response = client.post(self.update_role_approval_url(target.pk), data=params)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_is_approve(self, get_guest, get_manager, client):
    guest, _, _ = get_guest
    manager, _, _ = get_manager
    target = factories.RoleApprovalFactory(user=guest)
    params = {
      'is_approve': True
    }
    client.force_login(manager)
    response = client.post(self.update_role_approval_url(target.pk), data=params)
    user = UserModel.objects.get(pk=guest.pk)
    instance = models.RoleApproval.objects.get(pk=target.pk)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.role_change_requests_url
    assert user.role == models.RoleType.CREATOR
    assert instance.is_completed

  def test_is_not_approve(self, get_guest, get_manager, client):
    guest, _, _ = get_guest
    manager, _, _ = get_manager
    target = factories.RoleApprovalFactory(user=guest)
    params = {
      'is_approve': False
    }
    client.force_login(manager)
    response = client.post(self.update_role_approval_url(target.pk), data=params)
    user = UserModel.objects.get(pk=guest.pk)
    count = models.RoleApproval.objects.all().count()

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.role_change_requests_url
    assert user.role == models.RoleType.GUEST
    assert count == 0

# ====================
# = UpdateFriendPage =
# ====================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestUpdateFriendPage(Common):
  def test_without_authentication(self, client):
    response = client.get(self.update_friend_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_with_authentication(self, get_specific_users, client):
    codes = {
      'is-superuser': status.HTTP_403_FORBIDDEN,
      'is-manager': status.HTTP_403_FORBIDDEN,
      'is-creator': status.HTTP_200_OK,
      'is-guest': status.HTTP_200_OK,
    }
    key, user = get_specific_users
    status_code = codes[key]
    client.force_login(user)
    response = client.get(self.update_friend_url)

    assert response.status_code == status_code

  @pytest.fixture(params=['no-members', 'only-one-member', 'many-members'])
  def get_friend_pair(self, request, django_db_blocker):
    with django_db_blocker.unblock():
      _ = factories.UserFactory(is_active=True, is_staff=True, is_superuser=True)
      _ = factories.UserFactory(is_active=True, is_staff=True)
      _ = factories.UserFactory(is_active=False, is_staff=False)
      candidates = list(factories.UserFactory.create_batch(2, is_active=True))
      user = factories.UserFactory(is_active=True)

    config = {
      'no-members': [],
      'only-one-member': [str(candidates[0].pk)],
      'many-members': [str(candidates[0].pk), str(candidates[1].pk)],
    }
    friends = config[request.param]

    return user, friends

  def test_valid_access(self, client, get_friend_pair):
    user, friends = get_friend_pair
    client.force_login(user)
    params = {
      'friends': friends,
    }
    response = client.post(self.update_friend_url, data=params)
    updated_user = UserModel.objects.get(pk=user.pk)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.user_profile_url
    assert updated_user.friends.count() == len(friends)

# ===========================
# = IndividualGroupListPage =
# ===========================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestIndividualGroupListPage(Common):
  def test_without_authentication(self, client):
    response = client.get(self.individual_group_list_url)
    redirected_url = '{}?next={}'.format(self.login_url, self.individual_group_list_url)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == redirected_url

  def test_with_authentication(self, get_specific_users, client):
    codes = {
      'is-superuser': status.HTTP_403_FORBIDDEN,
      'is-manager': status.HTTP_403_FORBIDDEN,
      'is-creator': status.HTTP_200_OK,
      'is-guest': status.HTTP_200_OK,
    }
    key, user = get_specific_users
    status_code = codes[key]
    client.force_login(user)
    response = client.get(self.individual_group_list_url)

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
  def test_check_groups(self, client, number_of_groups, name):
    _ = factories.UserFactory(is_active=True, is_staff=True, is_superuser=True)
    _ = factories.UserFactory(is_active=True, is_staff=True)
    friends = list(factories.UserFactory.create_batch(5, is_active=True))
    user = factories.UserFactory(is_active=True, friends=friends)
    groups = factories.IndividualGroupFactory.create_batch(number_of_groups, owner=user, name=name, members=[friends[0], friends[2]])
    # Get access
    client.force_login(user)
    response = client.get(self.individual_group_list_url)
    lists = response.context['own_groups']

    assert response.status_code == status.HTTP_200_OK
    assert len(lists) == number_of_groups

# =============================
# = CreateIndividualGroupPage =
# =============================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestCreateIndividualGroupPage(Common):
  def test_without_authentication(self, client):
    response = client.get(self.create_group_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_with_authentication(self, get_specific_users, client):
    codes = {
      'is-superuser': status.HTTP_403_FORBIDDEN,
      'is-manager': status.HTTP_403_FORBIDDEN,
      'is-creator': status.HTTP_200_OK,
      'is-guest': status.HTTP_200_OK,
    }
    key, user = get_specific_users
    status_code = codes[key]
    client.force_login(user)
    response = client.get(self.create_group_url)

    assert response.status_code == status_code

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
  def test_valid_request(self, client, name, number_of_request_members):
    friends = list(factories.UserFactory.create_batch(3, is_active=True))
    user = factories.UserFactory(is_active=True, friends=friends)
    params = {
      'name': name,
      'members': [str(friends[idx].pk) for idx in range(number_of_request_members)],
    }
    client.force_login(user)
    response = client.post(self.create_group_url, data=params)
    _res = client.get(self.individual_group_list_url)
    groups = _res.context['own_groups']

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.individual_group_list_url
    assert len(groups) == 1
    assert groups[0].members.count() == number_of_request_members

# =============================
# = UpdateIndividualGroupPage =
# =============================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestUpdateIndividualGroupPage(Common):
  def test_without_authentication(self, get_guest, client):
    user, _, _ = get_guest
    instance = factories.IndividualGroupFactory(owner=user)
    response = client.get(self.update_group_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_with_authentication(self, get_guest, get_specific_users, client):
    codes = {
      'is-superuser': status.HTTP_403_FORBIDDEN,
      'is-staff': status.HTTP_403_FORBIDDEN,
      'is-manager': status.HTTP_403_FORBIDDEN,
      'is-creator': status.HTTP_403_FORBIDDEN,
      'is-guest': status.HTTP_200_OK, # Assumption: the target is owner
    }
    key, user = get_specific_users
    status_code = codes[key]
    owner, _, _ = get_guest
    instance = factories.IndividualGroupFactory(owner=owner)
    client.force_login(user)
    response = client.get(self.update_group_url(instance.pk))

    assert response.status_code == status_code

  def test_invalid_access(self, get_guest, get_creator, client):
    owner, _, _ = get_guest
    other, _, _ = get_creator
    instance = factories.IndividualGroupFactory(owner=owner)
    client.force_login(other)
    response = client.get(self.update_group_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

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
  def test_update_record(self, client, old_member_indices, new_member_indices):
    friends = list(factories.UserFactory.create_batch(5, is_active=True))
    user = factories.UserFactory(is_active=True, friends=friends)
    instance = factories.IndividualGroupFactory(owner=user, members=[friends[idx] for idx in old_member_indices])
    new_members = [friends[idx] for idx in new_member_indices]
    params = {
      'name': instance.name,
      'members': [str(item.pk) for item in new_members],
    }
    client.force_login(user)
    response = client.post(self.update_group_url(instance.pk), data=params)
    _instance = models.IndividualGroup.objects.get(pk=instance.pk)
    updated_members = list(_instance.members.all())
    _sort_record = lambda records: sorted(records, key=lambda item: str(item.pk))

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.individual_group_list_url
    assert all([
      str(estimated.pk) == str(exact.pk)
      for estimated, exact in zip(_sort_record(updated_members), _sort_record(new_members))
    ])

# =========================
# = DeleteIndividualGroup =
# =========================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestDeleteIndividualGroup(Common):
  def test_invalid_get_access(self, client):
    friends = list(factories.UserFactory.create_batch(2, is_active=True))
    user = factories.UserFactory(is_active=True, friends=friends)
    instance = factories.IndividualGroupFactory(owner=user, members=[friends[0]])
    client.force_login(user)
    response = client.get(self.delete_group_url(instance.pk))

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

  def test_without_authentication(self, client):
    friends = list(factories.UserFactory.create_batch(2, is_active=True))
    user = factories.UserFactory(is_active=True, friends=friends)
    instance = factories.IndividualGroupFactory(owner=user, members=[friends[0]])
    response = client.post(self.delete_group_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_invalid_access_by_other_user(self, client):
    friends = list(factories.UserFactory.create_batch(2, is_active=True))
    user = factories.UserFactory(is_active=True, friends=friends)
    other = factories.UserFactory(is_active=True)
    instance = factories.IndividualGroupFactory(owner=user, members=[friends[0]])
    client.force_login(other)
    response = client.post(self.delete_group_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_delete_record(self, client):
    friends = list(factories.UserFactory.create_batch(2, is_active=True))
    user = factories.UserFactory(is_active=True, friends=friends)
    instance = factories.IndividualGroupFactory(owner=user, members=[friends[0]])
    client.force_login(user)
    response = client.post(self.delete_group_url(instance.pk))

    with pytest.raises(models.IndividualGroup.DoesNotExist) as ex:
      _ = models.IndividualGroup.objects.get(pk=instance.pk)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.individual_group_list_url
    assert str(ex) != ''

# ===============================
# = IndividualGroupAjaxResponse =
# ===============================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestIndividualGroupAjaxResponse(Common):
  def test_get_access_without_authentication(self, client):
    response = client.get(self.ajax_get_options_url)

    assert response.status_code == status.HTTP_403_FORBIDDEN

  def test_get_access_with_authentication(self, get_specific_users, client):
    # get_specific_users
    status_patterns = {
      'is-superuser': status.HTTP_403_FORBIDDEN,
      'is-manager':   status.HTTP_403_FORBIDDEN,
      'is-creator':   status.HTTP_405_METHOD_NOT_ALLOWED,
      'is-guest':     status.HTTP_405_METHOD_NOT_ALLOWED,
    }
    key, user = get_specific_users
    status_code = status_patterns[key]
    client.force_login(user)
    response = client.get(self.ajax_get_options_url)

    assert response.status_code == status_code

  @pytest.fixture(params=['is-guest', 'is-creator'])
  def get_players_with_friends(self, request, django_db_blocker):
    with django_db_blocker.unblock():
      friends = list(factories.UserFactory.create_batch(4, is_active=True))
      guest = factories.UserFactory(is_active=True, friends=friends, role=models.RoleType.GUEST)
      creator = factories.UserFactory(is_active=True, friends=friends, role=models.RoleType.CREATOR)

    if request.param == 'is-guest':
      user = guest
    else:
      user = creator

    return user, friends

  @pytest.mark.parametrize([
    'arg_type',
    'expected_type',
  ], [
    ('only-group', 'specific'),
    ('no-data', 'all'),
  ], ids=lambda xs: str(xs))
  def test_post_access(self, get_players_with_friends, rf, arg_type, expected_type):
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
    params = patterns[arg_type]
    exact_arr = expected[expected_type]
    # Execute req-res
    request = rf.post(self.ajax_get_options_url, data=params, content_type='application/json')
    request.user = user
    ajax_view = views.IndividualGroupAjaxResponse.as_view()
    response = ajax_view(request)
    data = json.loads(response.content)
    options = data['options']

    assert response.status_code == status.HTTP_200_OK
    assert len(options) == len(exact_arr)
    assert g_compare_options(options, exact_arr)

  def test_invalid_request(self, client):
    friends = list(factories.UserFactory.create_batch(4, is_active=True))
    user = factories.UserFactory(is_active=True, friends=friends)
    params = {'group_pk': 123}
    # Execute req-res
    client.force_login(user)
    response = client.post(self.ajax_get_options_url, data=params, headers={'Content-Type': 'application/json'})
    data = json.loads(response.content)
    options = data['options']

    assert response.status_code == status.HTTP_200_OK
    assert len(options) == 0

# =======================
# = DownloadCreatorPage =
# =======================
@pytest.mark.account
@pytest.mark.view
@pytest.mark.django_db
class TestDownloadCreatorPage(Common):
  def test_check_get_access(self, get_specific_users, client):
    codes = {
      'is-superuser': status.HTTP_200_OK,
      'is-manager': status.HTTP_200_OK,
      'is-creator': status.HTTP_403_FORBIDDEN,
      'is-guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_specific_users
    client.force_login(user)
    response = client.get(self.download_creator_url)

    assert response.status_code == codes[key]

  def test_check_post_access(self, mocker, get_has_manager_role_members, client):
    output = {
      'rows': (row for row in [['hoge', 'abc', '123'], ['foo', 'xyz', '789']]),
      'header': ['Creator.pk', 'Screen name', 'Code'],
      'filename': 'creator-test1.csv',
    }
    mocker.patch('account.forms.CreatorDownloadForm.create_response_kwargs', return_value=output)
    user = get_has_manager_role_members
    params = {
      'filename': 'dummy-name',
    }
    expected = bytes('Creator.pk,Screen name,Code\nhoge,abc,123\nfoo,xyz,789\n', 'utf-8')
    # Post access
    client.force_login(user)
    response = client.post(self.download_creator_url, data=params)
    cookie = response.cookies.get('creator_download_status')
    attachment = response.get('content-disposition')
    stream = response.getvalue()

    assert response.has_header('content-disposition')
    assert output['filename'] == urllib.parse.unquote(attachment.split('=')[1].replace('"', ''))
    assert cookie.value == 'completed'
    assert expected in stream

  @pytest.mark.parametrize([
    'params',
    'err_msg',
  ], [
    ({}, 'This field is required'),
    ({'filename': '1'*129}, 'Ensure this value has at most 128 character'),
  ], ids=[
    'is-empty',
    'too-long-filename',
  ])
  def test_invalid_post_request(self, get_has_manager_role_members, client, params, err_msg):
    user = get_has_manager_role_members
    # Post access
    client.force_login(user)
    response = client.post(self.download_creator_url, data=params)
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(errors)