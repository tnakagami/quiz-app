import pytest
from webtest.app import AppError
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.urls import reverse
from app_tests import (
  status,
  factories,
  g_generate_item,
  g_compare_options,
)
from app_tests.integration_tests import get_current_path
from account.models import (
  RoleType,
  RoleApproval,
  IndividualGroup,
)
import urllib.parse

UserModel = get_user_model()

class Common:
  index_url = reverse('utils:index')

# ======================
# = Index/Login/Logout =
# ======================
@pytest.mark.webtest
@pytest.mark.django_db
class TestLoginLogout(Common):
  login_url = reverse('account:login')

  # Index page
  @pytest.mark.parametrize([
    'url_name',
  ], [
    ('utils:index',),
    ('account:alternative',),
  ], ids=[
    'index-url',
    'index-alternative-url',
  ])
  def test_access_to_index_page(self, csrf_exempt_django_app, url_name):
    app = csrf_exempt_django_app
    url = reverse(url_name)
    response = app.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert 'Index' in str(response)

  # Introduction page
  def test_can_move_to_introduction_page(self, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    page = app.get(self.index_url)
    response = page.click('Introduction')
    introduction_url = reverse('utils:introduction')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == introduction_url

  # Login page
  def test_can_move_to_login_page(self, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    page = app.get(self.index_url)
    response = page.click('Login')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.login_url

  def test_can_login(self, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    raw_password = 'test-hoge2pass'
    params = {
      'email': 'user@test.com',
      'password': raw_password,
    }
    user = UserModel.objects.create_user(is_active=True, **params)
    user.set_password(raw_password)
    user.save()
    # Get form and submit form
    forms = app.get(self.login_url).forms
    form = forms['login-form']
    form['username'] = params['email']
    form['password'] = params['password']
    response = form.submit().follow()

    assert response.status_code == status.HTTP_200_OK
    assert response.context['user'].email == params['email']

  @pytest.mark.parametrize([
    'role',
  ], [
    (RoleType.MANAGER, ),
    (RoleType.CREATOR, ),
    (RoleType.GUEST, ),
  ], ids=[
    'is-manager',
    'is-creator',
    'is-guest',
  ])
  def test_cannot_login_with_staff_permission(self, csrf_exempt_django_app, role):
    app = csrf_exempt_django_app
    raw_password = 'test-hoge2pass'
    params = {
      'email': 'user@test.com',
      'password': raw_password,
    }
    user = UserModel.objects.create_user(is_active=True, is_staff=True, role=role, **params)
    user.set_password(raw_password)
    user.save()
    # Get form and submit form
    forms = app.get(self.login_url).forms
    form = forms['login-form']
    form['username'] = params['email']
    form['password'] = params['password']
    response = form.submit()

    assert response.status_code == status.HTTP_200_OK
    assert 'The given user who has staff permission cannot login.' in str(response.context['form'].errors)

  def test_can_move_to_parent_page_from_login_page(self, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    page = app.get(self.login_url)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.index_url

  # Logout process
  @pytest.mark.django_db
  def test_can_logout(self, csrf_exempt_django_app, get_users):
    app = csrf_exempt_django_app
    _, user = get_users
    # Get form and submit form
    forms = app.get(self.index_url, user=user).forms
    form = forms['logout-form']
    response = form.submit().follow()

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.index_url

# ================
# = User Profile =
# ================
@pytest.mark.webtest
@pytest.mark.django_db
class TestUserProfile(Common):
  user_profile_url = reverse('account:user_profile')
  update_profile_url = reverse('account:update_profile')

  # User profile page
  def test_can_move_to_user_profile_page(self, csrf_exempt_django_app, get_users):
    app = csrf_exempt_django_app
    _, user = get_users
    page = app.get(self.index_url, user=user)
    response = page.click('User Profile')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.user_profile_url

  # Update user profile page
  def test_can_move_to_update_page(self, csrf_exempt_django_app, get_users):
    app = csrf_exempt_django_app
    _, user = get_users
    page = app.get(self.user_profile_url, user=user)
    response = page.click('Update user profile')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.update_profile_url

  def test_update_user_profile(self, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    params = {
      'email': 'user@test.com',
      'screen_name': 'sample',
    }
    new_screen_name = 'updated-name'
    user = factories.UserFactory(is_active=True, **params)
    # Get form and submit form
    forms = app.get(self.update_profile_url, user=user).forms
    form = forms['user-profile-form']
    form['screen_name'] = new_screen_name
    response = form.submit().follow()
    new_user = response.context['user']

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.user_profile_url
    assert new_user.email == params['email']
    assert new_user.screen_name == new_screen_name

  def test_can_move_to_parent_page_from_update_page(self, csrf_exempt_django_app, get_users):
    app = csrf_exempt_django_app
    _, user = get_users
    page = app.get(self.update_profile_url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.user_profile_url

# ========================
# = Account registration =
# ========================
@pytest.mark.webtest
@pytest.mark.django_db
class TestAccountRegistration(Common):
  create_account_url = reverse('account:create_account')

  def test_can_move_to_user_creation_page(self, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    page = app.get(self.index_url)
    response = page.click('Create account')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.create_account_url

  def test_can_move_to_parent_page_from_user_creation_page(self, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    page = app.get(self.create_account_url)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.index_url

  @pytest.mark.parametrize([
    'input_digest',
    'is_valid_expectation',
    'output_url',
  ], [
    ('hoge', True, reverse('account:done_account_creation')),
    ('foo', False, reverse('account:create_account')),
  ], ids=[
    'is-valid-request',
    'is-invalid-request',
  ])
  def test_send_post_request(self, mocker, csrf_exempt_django_app, input_digest, is_valid_expectation, output_url):
    mocker.patch('account.forms.get_digest', return_value='hoge')
    mocker.patch('account.models.EmailMessage.send', return_value=None)
    # Get form and submit form
    app = csrf_exempt_django_app
    forms = app.get(self.create_account_url).forms
    form = forms['create-account-form']
    form['email'] = 'hogehoge@example.com'
    form['password1'] = 'hoge2@foo3Bar0'
    form['password2'] = 'hoge2@foo3Bar0'
    form['screen_name'] = 'name-hoge'
    form['hash_sign'] = input_digest
    # Submit
    if is_valid_expectation:
      response = form.submit().follow()
    else:
      response = form.submit()

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == output_url

  @pytest.fixture
  def token_mocker(self, mocker):
    def inner(mock_config):
      user = UserModel.objects.create_user(is_active=False, email='hoge@hogehoge.test.com')
      mocker.patch('account.validators.CustomRegistrationTokenValidator.validate', **mock_config)
      mocker.patch('account.validators.CustomRegistrationTokenValidator.get_instance', return_value=user)
      url = reverse('account:complete_account_creation', kwargs={'token': 'hoge'})

      return user, url

    return inner

  def test_valid_token(self, token_mocker, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    user, url = token_mocker({'return_value': 'hoge'})
    response = app.get(url)
    target = UserModel.objects.get(pk=user.pk)

    assert response.status_code == status.HTTP_200_OK
    assert target.is_active

  def test_invalid_token(self, token_mocker, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    _, url = token_mocker({'side_effect': ValidationError('NG')})

    with pytest.raises(AppError) as ex:
      response = app.get(url)

    assert str(status.HTTP_400_BAD_REQUEST) in ex.value.args[0]

# ===================
# = Change password =
# ===================
@pytest.mark.webtest
@pytest.mark.django_db
class TestChangePassword(Common):
  parent_page_url = reverse('account:user_profile')
  update_password_url = reverse('account:update_password')

  def test_can_move_to_change_password_page(self, csrf_exempt_django_app, get_users):
    app = csrf_exempt_django_app
    _, user = get_users
    page = app.get(self.parent_page_url, user=user)
    response = page.click('Update password')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.update_password_url

  def test_can_move_to_parent_page_from_change_password_page(self, csrf_exempt_django_app, get_users):
    app = csrf_exempt_django_app
    _, user = get_users
    page = app.get(self.update_password_url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.parent_page_url

  @pytest.mark.parametrize([
    'new_password',
    'is_valid',
    'output_url',
  ], [
    ('hoge2@foo3Bar0', True, reverse('account:done_password_change')),
    ('hoge3@foo0goo1', False, reverse('account:update_password')),
  ], ids=[
    'is-valid-request',
    'is-invalid-request',
  ])
  def test_send_post_request(self, csrf_exempt_django_app, new_password, is_valid, output_url):
    old_password = 'a1H-2oG@3eF#'
    user = factories.UserFactory(is_active=True)
    user.set_password(old_password)
    user.save()
    # Get form and submit form
    app = csrf_exempt_django_app
    forms = app.get(self.update_password_url, user=user).forms
    form = forms['update-password-form']
    form['old_password'] = old_password
    form['new_password1'] = new_password
    form['new_password2'] = 'hoge2@foo3Bar0'
    # Submit
    if is_valid:
      response = form.submit().follow()
    else:
      response = form.submit()

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == output_url

# ==================
# = Reset password =
# ==================
@pytest.mark.webtest
@pytest.mark.django_db
class TestResetPassword(Common):
  parent_page_url = reverse('account:login')
  reset_password_url = reverse('account:reset_password')

  def test_can_move_to_reset_password_page(self, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    page = app.get(self.parent_page_url)
    response = page.click('Forget own password')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.reset_password_url

  def test_can_move_to_parent_page_from_reset_password_page(self, csrf_exempt_django_app):
    app = csrf_exempt_django_app
    page = app.get(self.reset_password_url)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.parent_page_url

  def test_send_post_request(self, mocker, csrf_exempt_django_app):
    email_mock = mocker.patch('django.contrib.auth.forms.EmailMultiAlternatives.send', return_value=None)
    user = factories.UserFactory(is_active=True, email='hoge@good.email.com')
    # Get form and submit form
    app = csrf_exempt_django_app
    forms = app.get(self.reset_password_url).forms
    form = forms['reset-password-form']
    form['email'] = 'hoge@good.email.com'
    response = form.submit().follow()

    assert response.status_code == status.HTTP_200_OK
    assert email_mock.call_count == 1

  @pytest.mark.parametrize([
    'email',
    'is_active',
  ], [
    ('hoge@good.email.com', False),
    ('nobody@bad.email', True),
  ], ids=[
    'user-is-not-active',
    'user-does-not-exist',
  ])
  def test_send_invalid_post_request(self, mocker, csrf_exempt_django_app, email, is_active):
    email_mock = mocker.patch('django.contrib.auth.forms.EmailMultiAlternatives.send', return_value=None)
    user = factories.UserFactory(is_active=is_active, email='hoge@good.email.com')
    # Get form and submit form
    app = csrf_exempt_django_app
    forms = app.get(self.reset_password_url).forms
    form = forms['reset-password-form']
    form['email'] = email
    response = form.submit()

    assert response.status_code == status.HTTP_200_OK
    assert email_mock.call_count == 0

  @pytest.fixture
  def get_confirm_page_url(self):
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
    'config',
    'is_valid',
  ], [
    ({'new_password1': 'h2o!nH3@foo+', 'new_password2': 'h2o!nH3@foo+'}, True),
    ({'new_password1': 'h2o!nH3@foo+'}, False),
    ({}, False),
  ], ids=[
    'valid-passwords',
    'mismatch-password',
    'no-passwords',
  ])
  def test_check_password_for_confirm_page(self, get_confirm_page_url, csrf_exempt_django_app, config, is_valid):
    app = csrf_exempt_django_app
    user = factories.UserFactory(is_active=True, email='hoge@good.email.com')
    url = get_confirm_page_url(user)
    forms = app.get(url).follow().forms
    form = forms['reset-password-form']
    # Post request
    for key, val in config.items():
      form[key] = val
    if is_valid:
      response = form.submit().follow()
      output_url = reverse('account:complete_password_reset')
    else:
      response = form.submit()
      output_url = get_confirm_page_url(user, is_GET=False)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == output_url

# =========================
# = Download creator list =
# =========================
@pytest.mark.webtest
@pytest.mark.django_db
class TestDownloadCreator(Common):
  form_view_url = reverse('account:download_creator')

  def test_can_move_to_download_page(self, csrf_exempt_django_app, get_has_manager_role_user):
    app = csrf_exempt_django_app
    _, user = get_has_manager_role_user
    page = app.get(self.index_url, user=user)
    response = page.click('Download creator list')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.form_view_url

  def test_cannot_move_to_download_page(self, csrf_exempt_django_app, get_players):
    app = csrf_exempt_django_app
    _, user = get_players
    page = app.get(self.index_url, user=user)

    with pytest.raises(IndexError):
      _ = page.click('Download creator list')

  def test_can_move_to_parent_page_from_download_page(self, csrf_exempt_django_app, get_has_manager_role_user):
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    page = app.get(self.form_view_url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.index_url

  @pytest.mark.parametrize([
    'filename',
    'exact_fname',
  ], [
    ('hoge-test', 'creator-hoge-test.csv'),
    ('foo-test.csv', 'creator-foo-test.csv'),
    ('.csv', 'creator-20200102-100518.csv'),
  ], ids=[
    'normal-name',
    'with-extensions',
    'only-extensions',
  ])
  def test_send_post_request(self, mocker, csrf_exempt_django_app, get_has_manager_role_user, filename, exact_fname):
    mocker.patch('account.forms.generate_default_filename', return_value='20200102-100518')
    _, user = get_has_manager_role_user
    creators = factories.UserFactory.create_batch(5, is_active=True, role=RoleType.CREATOR)
    creators = UserModel.objects.filter(pk__in=[obj.pk for obj in creators])
    mocker.patch('account.models.User.objects.collect_creators', return_value=creators)
    # Create expected value
    lines = '\n'.join(['{},{},{}'.format(str(obj.pk), str(obj), obj.code) for obj in creators.order_by('email')]) + '\n'
    expected = {
      'data': bytes('Creator.pk,Screen name,Code\n' + lines, 'utf-8'),
      'filename': exact_fname,
    }
    # Send post request
    app = csrf_exempt_django_app
    forms = app.get(self.form_view_url, user=user).forms
    form = forms['creator-download-form']
    form['filename'] = filename
    response = form.submit()
    cookie = response.client.cookies.get('creator_download_status')
    attachment = response['content-disposition']
    stream = response.content

    assert expected['filename'] == urllib.parse.unquote(attachment.split('=')[1].replace('"', ''))
    assert cookie.value == 'completed'
    assert expected['data'] in stream

  def test_send_invalid_request(self, csrf_exempt_django_app, get_has_manager_role_user):
    _, user = get_has_manager_role_user
    # Send post request
    app = csrf_exempt_django_app
    forms = app.get(self.form_view_url, user=user).forms
    form = forms['creator-download-form']
    form['filename'] = '1'*129
    response = form.submit()
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert 'Ensure this value has at most 128 character' in str(errors)

# ===============
# = Change role =
# ===============
@pytest.mark.webtest
@pytest.mark.django_db
class TestChangeRole(Common):
  profile_url = reverse('account:user_profile')
  role_list_url = reverse('account:role_change_requests')
  create_role_url = reverse('account:create_role_change_request')
  update_role_url = lambda _self, pk: reverse('account:update_role_approval', kwargs={'pk': pk})

  def test_can_move_to_change_role_page(self, csrf_exempt_django_app, get_manager):
    app = csrf_exempt_django_app
    user = get_manager
    page = app.get(self.index_url, user=user)
    response = page.click('Role change request')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.role_list_url

  def test_cannot_move_to_change_role_page(self, csrf_exempt_django_app, get_players):
    app = csrf_exempt_django_app
    _, user = get_players
    page = app.get(self.index_url, user=user)

    with pytest.raises(IndexError):
      _ = page.click('Check/update role change requests')

  def test_can_move_to_role_change_request_page(self, csrf_exempt_django_app, get_guest):
    user = get_guest
    app = csrf_exempt_django_app
    page = app.get(self.profile_url, user=user)
    response = page.click('Change own role to "CREATOR"')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.create_role_url

  def test_can_move_to_parent_page_from_role_change_request_page(self, csrf_exempt_django_app, get_guest):
    user = get_guest
    app = csrf_exempt_django_app
    page = app.get(self.create_role_url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.profile_url

  def test_cannot_move_to_role_change_request_page(self, csrf_exempt_django_app, get_users):
    key, user = get_users

    if key == 'guest':
      _ = factories.RoleApprovalFactory(user=user, is_completed=False)
    app = csrf_exempt_django_app

    with pytest.raises(AppError) as ex:
      _ = app.get(self.create_role_url, user=user)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  def test_send_post_request(self, csrf_exempt_django_app, get_guest):
    user = get_guest
    app = csrf_exempt_django_app
    forms = app.get(self.create_role_url, user=user).forms
    form = forms['change-role-form']
    response = form.submit().follow()
    all_counts = RoleApproval.objects.filter(user=user).count()

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.profile_url
    assert all_counts == 1

  @pytest.mark.parametrize([
    'is_approve',
    'count',
  ], [
    (True, 1),
    (False, 0),
  ], ids=[
    'is-approve',
    'is-not-approve',
  ])
  def test_approve_role_change_request(self, csrf_exempt_django_app, get_manager, is_approve, count):
    guest = factories.UserFactory(is_active=True, role=RoleType.GUEST)
    instance = factories.RoleApprovalFactory(user=guest, is_completed=False)
    user = get_manager
    app = csrf_exempt_django_app
    url = self.update_role_url(instance.pk)
    response = app.post(url, {'is_approve': is_approve}, user=user).follow()
    all_counts = RoleApproval.objects.filter(user=guest).count()

    assert response.status_code == status.HTTP_200_OK
    assert all_counts == count

# =================
# = Update friend =
# =================
@pytest.mark.webtest
@pytest.mark.django_db
class TestUpdateFriends(Common):
  profile_url = reverse('account:user_profile')
  update_friend_url = reverse('account:update_friend')

  def test_can_move_to_update_friend(self, csrf_exempt_django_app, get_players):
    _, user = get_players
    app = csrf_exempt_django_app
    page = app.get(self.profile_url, user=user)
    response = page.click('Register/Unregister friends')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.update_friend_url

  def test_cannot_move_to_update_friend(self, csrf_exempt_django_app, get_has_manager_role_user):
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    page = app.get(self.profile_url, user=user)

    with pytest.raises(IndexError):
      _ = page.click('Register/Unregister friends')

  def test_can_move_to_parent_page_from_friend_page(self, csrf_exempt_django_app, get_players):
    _, user = get_players
    app = csrf_exempt_django_app
    page = app.get(self.update_friend_url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.profile_url

  def test_send_post_request(self, csrf_exempt_django_app, get_players):
    creators = list(factories.UserFactory.create_batch(2, is_active=True, role=RoleType.CREATOR))
    guests = list(factories.UserFactory.create_batch(3, is_active=True, role=RoleType.GUEST))
    _, user = get_players
    ids = [str(creators[0].pk), str(guests[0].pk)]
    app = csrf_exempt_django_app
    forms = app.get(self.update_friend_url, user=user).forms
    form = forms['friend-form']
    form['friends'] = ids
    response = form.submit().follow()
    target = UserModel.objects.get(pk=user.pk)
    all_friends = target.friends.all()

    assert response.status_code == status.HTTP_200_OK
    assert all_friends.count() == 2
    assert all([str(user.pk) in ids for user in all_friends])

  def test_invalid_post_request(self, csrf_exempt_django_app, get_guest, get_friends):
    # In the case of that target user has individual group which includes user's friends
    other = get_guest
    friends = get_friends
    friends = UserModel.objects.filter(pk__in=[val.pk for val in friends]).order_by('pk')
    user = factories.UserFactory(
      is_active=True,
      role=RoleType.CREATOR,
      friends=friends,
    )
    instance = factories.IndividualGroupFactory(owner=user, name='hoge-foo', members=friends)
    app = csrf_exempt_django_app
    forms = app.get(self.update_friend_url, user=user).forms
    form = forms['friend-form']
    form['friends'] = [str(other.pk)]
    response = form.submit()
    errors = response.context['form'].errors
    names = ','.join([str(user) for user in friends])
    err_msg = f'You need to select relevant friends because the individual group &quot;hoge-foo&quot; has {names} member(s).'

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(errors)

# ====================
# = Individual group =
# ====================
@pytest.mark.webtest
@pytest.mark.django_db
class TestIndividualGroup(Common):
  profile_url = reverse('account:user_profile')
  group_list_url = reverse('account:individual_group_list')
  create_group_url = reverse('account:create_group')
  update_group_url = lambda _self, pk: reverse('account:update_group', kwargs={'pk': pk})
  delete_group_url = lambda _self, pk: reverse('account:delete_group', kwargs={'pk': pk})

  def test_can_move_to_group_list(self, csrf_exempt_django_app, get_players):
    _, user = get_players
    app = csrf_exempt_django_app
    page = app.get(self.profile_url, user=user)
    response = page.click('Create/Edit/Delete indivitual groups')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.group_list_url

  def test_cannot_move_to_group_list(self, csrf_exempt_django_app, get_has_manager_role_user):
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    page = app.get(self.profile_url, user=user)

    with pytest.raises(IndexError):
      _ = page.click('Create/Edit/Delete indivitual groups')

  def test_can_move_to_create_page(self, csrf_exempt_django_app, get_players):
    _, user = get_players
    app = csrf_exempt_django_app
    page = app.get(self.group_list_url, user=user)
    response = page.click('Create a new group')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.create_group_url

  def test_can_move_to_parent_page_from_create_page(self, csrf_exempt_django_app, get_players):
    _, user = get_players
    app = csrf_exempt_django_app
    page = app.get(self.create_group_url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.group_list_url

  def test_send_create_request(self, csrf_exempt_django_app, get_players, get_friends):
    friends = get_friends
    _, user = get_players
    user = factories.UserFactory(is_active=True, role=user.role, friends=friends)
    app = csrf_exempt_django_app
    forms = app.get(self.create_group_url, user=user).forms
    form = forms['group-form']
    form['name'] = 'hogehoge-foo'
    form['members'] = [str(friends[0].pk)]
    response = form.submit().follow()
    all_counts = IndividualGroup.objects.filter(owner=user).count()

    assert response.status_code == status.HTTP_200_OK
    assert all_counts == 1

  def test_invalid_create_request(self, csrf_exempt_django_app, get_guest, get_friends, get_players):
    other = get_guest
    friends = get_friends
    _, user = get_players
    user = factories.UserFactory(is_active=True, role=user.role, friends=friends)
    app = csrf_exempt_django_app
    forms = app.get(self.create_group_url, user=user).forms
    form = forms['group-form']
    form['name'] = 'hogehoge-foo'

    with pytest.raises(ValueError):
      form['members'] = [str(other.pk)]

  def test_can_move_to_edit_page(self, csrf_exempt_django_app, get_friends, get_players):
    friends = get_friends
    _, user = get_players
    user = factories.UserFactory(is_active=True, role=user.role, friends=friends)
    instance = factories.IndividualGroupFactory(owner=user, members=[friends[0], friends[1]])
    app = csrf_exempt_django_app
    page = app.get(self.group_list_url, user=user)
    response = page.click('Edit')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.update_group_url(instance.pk)

  def test_cannot_move_to_edit_page(self, csrf_exempt_django_app, get_players):
    _, user = get_players
    app = csrf_exempt_django_app
    page = app.get(self.group_list_url, user=user)

    with pytest.raises(IndexError):
      _ = page.click('Edit')

  def test_send_update_request(self, csrf_exempt_django_app, get_friends, get_players):
    friends = get_friends
    _, user = get_players
    user = factories.UserFactory(is_active=True, role=user.role, friends=friends)
    instance = factories.IndividualGroupFactory(owner=user, members=[friends[0], friends[1]])
    app = csrf_exempt_django_app
    url = self.update_group_url(instance.pk)
    forms = app.get(url, user=user).forms
    form = forms['group-form']
    form['name'] = 'hogehoge-foo'
    form['members'] = [str(friends[2].pk)]
    response = form.submit().follow()
    queryset = IndividualGroup.objects.filter(owner=user)
    target = queryset.first()

    assert response.status_code == status.HTTP_200_OK
    assert queryset.count() == 1
    assert all([user.pk == friends[2].pk for user in target.members.all()])

  def test_invalid_update_request(self, csrf_exempt_django_app, get_guest, get_friends, get_players):
    other = get_guest
    friends = get_friends
    _, user = get_players
    user = factories.UserFactory(is_active=True, role=user.role, friends=friends)
    instance = factories.IndividualGroupFactory(owner=user, members=[friends[0], friends[1]])
    app = csrf_exempt_django_app
    url = self.update_group_url(instance.pk)
    forms = app.get(url, user=user).forms
    form = forms['group-form']
    form['name'] = 'hogehoge-foo'

    with pytest.raises(ValueError):
      form['members'] = [str(other.pk)]

  @pytest.mark.parametrize([
    'config',
  ], [
    ({'role': RoleType.GUEST,   'is_staff': True,  'is_superuser': True}, ),
    ({'role': RoleType.MANAGER, 'is_staff': False, 'is_superuser': False}, ),
    ({'role': RoleType.CREATOR, 'is_staff': False, 'is_superuser': False}, ),
    ({'role': RoleType.GUEST,   'is_staff': False, 'is_superuser': False}, ),
  ], ids=[
    'is-superuser',
    'is-manager',
    'is-creator',
    'is-guest',
  ])
  def test_cannot_get_access_of_delete_request(self, csrf_exempt_django_app, get_friends, config):
    friends = get_friends
    user = factories.UserFactory(is_active=True, friends=friends, **config)
    instance = factories.IndividualGroupFactory(owner=user, members=[friends[0], friends[1]])
    app = csrf_exempt_django_app
    url = self.delete_group_url(instance.pk)

    with pytest.raises(AppError) as ex:
      _ = app.get(url, user=user)

    assert str(status.HTTP_405_METHOD_NOT_ALLOWED) in ex.value.args[0]

  def test_send_delete_request(self, csrf_exempt_django_app, get_players, get_friends):
    _, user = get_players
    friends = get_friends
    user = factories.UserFactory(
      is_active=True,
      role=user.role,
      friends=friends,
    )
    instance = factories.IndividualGroupFactory(owner=user, members=[friends[0], friends[1]])
    app = csrf_exempt_django_app
    url = self.delete_group_url(instance.pk)
    response = app.post(url, user=user).follow()
    all_counts = IndividualGroup.objects.filter(owner=user).count()

    assert response.status_code == status.HTTP_200_OK
    assert all_counts == 0

  def test_invalid_delete_request(self, csrf_exempt_django_app, get_players, get_friends):
    _, user = get_players
    friends = get_friends
    user = factories.UserFactory(
      is_active=True,
      role=user.role,
      friends=friends,
    )
    other = factories.UserFactory(
      is_active=True,
      role=RoleType.GUEST,
      friends=friends,
    )
    instance = factories.IndividualGroupFactory(owner=other, members=[friends[0], friends[1]])
    app = csrf_exempt_django_app
    url = self.delete_group_url(instance.pk)

    with pytest.raises(AppError) as ex:
      _ = app.post(url, user=user)
    all_counts = IndividualGroup.objects.filter(owner=other).count()

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]
    assert all_counts == 1

# ===============================
# = IndividualGroupAjaxResponse =
# ===============================
@pytest.mark.webtest
@pytest.mark.django_db
class TestGroupAjax(Common):
  ajax_url = reverse('account:ajax_get_options')

  def test_cannot_get_access(self, csrf_exempt_django_app):
    app = csrf_exempt_django_app

    with pytest.raises(AppError) as ex:
      _ = app.get(self.ajax_url)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  def test_cannot_get_access_with_authentication(self, csrf_exempt_django_app, get_users):
    app = csrf_exempt_django_app
    exact_types = {
      'superuser': status.HTTP_403_FORBIDDEN,
      'manager': status.HTTP_403_FORBIDDEN,
      'creator': status.HTTP_405_METHOD_NOT_ALLOWED,
      'guest': status.HTTP_405_METHOD_NOT_ALLOWED,
    }
    key, user = get_users

    with pytest.raises(AppError) as ex:
      _ = app.get(self.ajax_url, user=user)

    assert str(exact_types[key]) in ex.value.args[0]

  def test_send_post_request(self, csrf_exempt_django_app, get_players, get_friends):
    _, user = get_players
    friends = get_friends
    user = factories.UserFactory(
      is_active=True,
      role=user.role,
      friends=friends,
    )
    members = [friends[0], friends[1]]
    instance = factories.IndividualGroupFactory(owner=user, members=members)
    app = csrf_exempt_django_app
    response = app.post_json(self.ajax_url, dict(group_pk=str(instance.pk)), user=user)
    data = response.json
    expected = g_generate_item(members, False)

    assert response.status_code == status.HTTP_200_OK
    assert 'options' in data.keys()
    assert g_compare_options(expected, data['options'])

  def test_invalid_post_request(self, csrf_exempt_django_app, get_guest):
    user = factories.UserFactory(is_active=True, role=RoleType.GUEST)
    other = get_guest
    app = csrf_exempt_django_app
    response = app.post_json(self.ajax_url, dict(owner_pk=str(other.pk)), user=user)
    data = response.json
    expected = g_generate_item(UserModel.objects.collect_valid_friends(user), False)

    assert response.status_code == status.HTTP_200_OK
    assert 'options' in data.keys()
    assert g_compare_options(expected, data['options'])