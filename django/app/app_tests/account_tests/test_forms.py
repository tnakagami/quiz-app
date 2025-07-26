import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.urls import reverse
from app_tests import (
  factories,
  g_generate_item,
  g_compare_options,
)
from account import forms, models
import json

UserModel = get_user_model()
g_complex_passwd = 'h2o$Jax3#1Pi'
g_wrong_password = 'h0o$jAx4#Pi5'

# ====================
# = Global functions =
# ====================
@pytest.mark.account
@pytest.mark.form
@pytest.mark.parametrize([
  'forwarding_port',
  'expected',
], [
  ('', ''),
  ('8234', ':8234'),
], ids=[
  'set-forwarding-port-number',
  'does-not-set-forwarding-port-number',
])
def test_check_get_forwarding_port(settings, forwarding_port, expected):
  settings.NGINX_FORWARDING_PORT = forwarding_port
  port_num = forms._get_forwarding_port()

  assert port_num == expected

@pytest.mark.account
@pytest.mark.form
def test_valid_digest_validator(mocker):
  exact_digest = 'abc123'
  mocker.patch('account.forms.get_digest', return_value=exact_digest)

  try:
    forms._validate_hash_sign(exact_digest)
  except Exception as ex:
    pytest.fail(f'Unexpected Error: {ex}')

@pytest.mark.account
@pytest.mark.form
def test_invalid_digest_validator(mocker):
  mocker.patch('account.forms.get_digest', return_value='abc123')
  err_msg = 'Invalid a digest value.'

  with pytest.raises(ValidationError) as ex:
    forms._validate_hash_sign('xyz')

  assert err_msg in ex.value.args

# =============
# = LoginForm =
# =============
@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'email',
  'password',
  'is_staff',
  'is_valid',
], [
  ('hoge@example.com', 'test-hoge2pass',  False, True),
  ('nobody@foo.com',   'test-hoge2pass',  False, False),
  ('hoge@example.com', 'wrong-pass2word', False, False),
  (              None, 'test-hoge2pass',  False, False),
  ('hoge@example.com',              None, False, False),
  ('hoge@example.com', 'test-hoge2pass',  True,  False),
], ids=[
  'can-login',
  'invalid-email',
  'invalid-password',
  'email-is-empty',
  'password-is-empty',
  'is-staff-user',
])
def test_check_login_form(email, password, is_staff, is_valid):
  raw_password = 'test-hoge2pass'
  user = factories.UserFactory(
    email='hoge@example.com',
    is_active=True,
    is_staff=is_staff,
  )
  user.set_password(raw_password)
  user.save()

  # Create form parameters
  params = {}
  if email is not None:
    params['username'] = email
  if password is not None:
    params['password'] = password
  form = forms.LoginForm(data=params)

  assert form.is_valid() == is_valid

# ====================
# = UserCreationForm =
# ====================
@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'email',
  'password1',
  'password2',
  'screen_name',
  'hash_sign',
  'mock_type',
  'is_valid',
], [
  ('hoge@example.com',   g_complex_passwd, g_complex_passwd, 'test-hoge', 'hoge', 'mock_retval', True),
  ('hoge@example.com',   g_complex_passwd, g_complex_passwd,        None, 'hoge', 'mock_retval', True),
  (              None,   g_complex_passwd, g_complex_passwd, 'test-hoge', 'hoge', 'mock_retval', False),
  ('hoge@example.com',               None,             None, 'test-hoge', 'hoge', 'mock_retval', False),
  ('hoge@example.com',   g_complex_passwd,             None, 'test-hoge', 'hoge', 'mock_retval', False),
  ('hoge@example.com',               None, g_complex_passwd, 'test-hoge', 'hoge', 'mock_retval', False),
  ('hoge@example.com',   g_complex_passwd, g_complex_passwd, 'test-hoge',   None, 'mock_retval', False),
  ('wrong-email-format', g_complex_passwd, g_complex_passwd, 'test-hoge', 'hoge', 'mock_retval', False),
  ('hoge@example.com',   g_complex_passwd, g_wrong_password, 'test-hoge', 'hoge', 'mock_retval', False),
  ('hoge@example.com',   'weak-passWord0', 'weak-passWord0', 'test-hoge', 'hoge', 'mock_weakpw', False),
  ('hoge@example.com',   g_complex_passwd, g_complex_passwd, 'test-hoge', 'hoge', 'mock_exception', False),
], ids=[
  'valid-user-information',
  'screen-name-is-empty',
  'email-is-empty',
  'both-passwords-are-empty',
  'password1-is-empty',
  'password2-is-empty',
  'digest-is-empty',
  'invalid-email-format',
  'does-not-match-passwords',
  'enter-weak-password',
  'digest-is-wrong',
])
def test_check_user_creation_form(mocker, email, password1, password2, screen_name, hash_sign, mock_type, is_valid):
  # Define form parameters
  params = {
    'email': email,
    'password1': password1,
    'password2': password2,
    'screen_name': screen_name,
    'hash_sign': hash_sign,
  }
  # If input value is None, then delete the key form `params` variable
  _keys = list(params.keys())
  for key in _keys:
    if params[key] is None:
      del params[key]
  # Create form
  form = forms.UserCreationForm(data=params)
  err_hash_msg = 'Invalid a digest value.'
  # Setup magic mock
  if mock_type == 'mock_retval':
    # Replace validator setting of form's field
    field = form.fields['hash_sign']
    mocker.patch.object(field, 'validators', return_value=[])
    callback = lambda errs: err_hash_msg not in str(errs)
  elif mock_type == 'mock_exception':
    # Raise exception in validate method
    mocker.patch('account.forms.CustomDigestValidator.validate', side_effect=ValidationError(err_hash_msg))
    callback = lambda errs: err_hash_msg in str(errs)
  else:
    # Raise exception in validate method
    mocker.patch('account.validators.CustomPasswordValidator.validate', side_effect=ValidationError('weak-password'))
    callback = lambda errs: 'weak-password' in str(errs)

  assert form.is_valid() == is_valid
  assert callback(form.errors)

@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'is_active',
  'exact_val',
], [
  (True, True),
  (False, False),
], ids=[
  'does-not-remove-target-user',
  'do-remove-target-user',
])
def test_check_clean_email_method_of_user_creation_form(is_active, exact_val):
  email = 'hoge@example.com'
  _ = factories.UserFactory(email=email, is_active=is_active)

  # Create form parameters
  params = {
    'email': email,
    'password1': g_complex_passwd,
    'password2': g_complex_passwd,
    'hash_sign': 'hoge',
  }
  form = forms.UserCreationForm(data=params)
  form.cleaned_data = {'email': email}
  form.clean_email()
  estimated = UserModel.objects.filter(email=email).exists()

  assert estimated == exact_val

@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
def test_check_save_method_of_user_creation_form(mocker):
  params = {
    'email': 'hoge@example.com',
    'password1': g_complex_passwd,
    'password2': g_complex_passwd,
    'hash_sign': 'hoge',
  }
  # Create form and mock specific field
  form = forms.UserCreationForm(data=params)
  mocker.patch.object(form.fields['hash_sign'], 'validators', return_value=[])
  is_valid = form.is_valid()
  # Call save method
  user = form.save()

  assert is_valid
  assert not user.is_active

@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'port_num',
], [
  (':8443',),
  ('',),
], ids=[
  'set-port-number',
  'does-not-set-port-number',
])
def test_check_send_email_method_of_user_creation_form(mocker, port_num):
  class FakeObj:
    def __init__(self):
      self.scheme = 'https'
      self.domain = 'foo'
      self.token = 'test-token'

  # Create user
  user = factories.UserFactory(email='hoge@example.com', is_active=False)
  # Setup mock
  fake_obj = FakeObj()
  mocker.patch('account.forms.get_current_site', return_value=fake_obj)
  mocker.patch('account.forms.dumps', return_value=fake_obj.token)
  mocker.patch('account.forms._get_forwarding_port', return_value=port_num)
  email_user_mock = mocker.patch.object(user, 'email_user', return_value=None)
  # Call send_email
  form = forms.UserCreationForm()
  config = {
    'timelimit': 3,
    'subject_template_name': 'account/mail_template/provisional_registration/subject.txt',
    'email_template_name': 'account/mail_template/provisional_registration/message.txt',
    'user': user,
  }
  form.send_email(fake_obj, config)
  args, _ = email_user_mock.call_args
  subject, message = args

  # Prepare for expected values
  relevant_link = reverse('account:complete_account_creation', kwargs={'token': fake_obj.token})
  exact_url = f'{fake_obj.scheme}://{fake_obj.domain}{port_num}{relevant_link}'
  exact_timelimit = f'The above url is valid for 3 minutes'  # Based on "{'timelimit': 3,} in config"
  # Check whether this method is only called at once
  email_user_mock.assert_called_once()
  assert 'Quiz app - Account registration' in subject
  assert user.email in message
  assert exact_url in message
  assert exact_timelimit in message

# ===================
# = UserProfileForm =
# ===================
@pytest.mark.account
@pytest.mark.form
@pytest.mark.parametrize([
  'params',
  'is_valid',
], [
  ({'screen_name':  'name'}, True),
  ({'screen_name': '1'*128}, True),
  ({'screen_name':      ''}, True),
  ({'screen_name':    None}, True),
  ({                      }, True),
  ({'screen_name': '1'*129}, False),
], ids=[
  'normal-case',
  'name-length-eq-128',
  'name-is-empty',
  'name-is-none',
  'name-is-not-set',
  'name-length-eq-129',
])
def test_user_profile_form(params, is_valid):
  form = forms.UserProfileForm(data=params)

  assert form.is_valid() is is_valid

# ============================
# = CustomPasswordChangeForm =
# ============================
@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'params',
  'is_valid',
], [
  ({'old_password': 'a1B-2cD@3eF#', 'new_password1': 'h2o!nH3@So4+', 'new_password2': 'h2o!nH3@So4+'},  True),
  ({'old_password': 'a1B-222@3eF#', 'new_password1': 'h2o!nH3@So4+', 'new_password2': 'h2o!nH3@So4+'}, False),
  ({'old_password': 'a1B-2cD@3eF#', 'new_password1': 'h2o!nH3@So4+', 'new_password2': 'nH3@So4+h2o!'}, False),
  ({                                'new_password1': 'h2o!nH3@So4+', 'new_password2': 'nH3@So4+h2o!'}, False),
  ({'old_password': 'a1B-2cD@3eF#',                                  'new_password2': 'h2o!nH3@So4+'}, False),
  ({'old_password': 'a1B-2cD@3eF#', 'new_password1': 'h2o!nH3@So4+'                                 }, False),
  ({'old_password': 'a1B-2cD@3eF#', 'new_password1': 'a1B-2cD@3eF#', 'new_password2': 'a1B-2cD@3eF#'}, False),
], ids=[
  'valid-case',
  'mismatch-old-password',
  'mismatch-new-password',
  'old-password-is-empty',
  'new-password1-is-empty',
  'new-password2-is-empty',
  'use-same-password',
])
def test_password_change_form(params, is_valid):
  old_password = 'a1B-2cD@3eF#'
  user = factories.UserFactory()
  user.set_password(old_password)
  form = forms.CustomPasswordChangeForm(data=params, user=user)

  assert form.is_valid() == is_valid

# ===========================
# = CustomPasswordResetForm =
# ===========================
@pytest.mark.account
@pytest.mark.form
@pytest.mark.parametrize([
  'email',
  'is_valid',
], [
  ('hoge@example.com', True),
  ('{}@hoge.com'.format('1'*119), True),
  ('{}@hoge.com'.format('1'*120), False),
], ids=[
  'norma-email-address',
  'is-max-length',
  'over-max-length',
])
def test_check_password_reset_form(email, is_valid):
  params = {
    'email': email,
  }
  form = forms.CustomPasswordResetForm(data=params)

  assert form.is_valid() == is_valid

def test_check_save_method(mocker):
  class FakeObj:
    def __init__(self):
      self.domain = 'hoge'
  # Define test code
  fake_obj = FakeObj()
  mocker.patch('account.forms.get_current_site', return_value=fake_obj)
  mocker.patch('account.forms._get_forwarding_port', return_value=':3256')
  save_mock = mocker.patch('django.contrib.auth.forms.PasswordResetForm.save', return_value=None)
  params = {
    'email': 'hoge@example.com',
  }
  form = forms.CustomPasswordResetForm(data=params)
  form.save(request=None)
  _, kwargs = save_mock.call_args
  domain_override = kwargs.get('domain_override')
  expected = 'hoge:3256'

  assert domain_override == expected

# =========================
# = CustomSetPasswordForm =
# =========================
@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'params',
  'is_valid',
], [
  ({'new_password1': 'h2o!nH3@So4+', 'new_password2': 'h2o!nH3@So4+'},  True),
  ({'new_password1': 'h2o!nH3@So4+', 'new_password2': 'nH3@So4+h2o!'}, False),
  ({                                 'new_password2': 'h2o!nH3@So4+'}, False),
  ({'new_password1': 'h2o!nH3@So4+'                                 }, False),
], ids=[
  'valid-case',
  'mismatch-new-password',
  'new-password1-is-empty',
  'new-password2-is-empty',
])
def test_set_password_form(params, is_valid):
  user = factories.UserFactory()
  form = forms.CustomSetPasswordForm(data=params, user=user)

  assert form.is_valid() == is_valid

# =========================
# = RoleChangeRequestForm =
# =========================
@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
def test_valid_clean_method_of_role_change_request_form(mocker):
  mocker.patch('account.models.RoleApproval.has_request_permission', return_value=True)
  user = factories.UserFactory()
  form = forms.RoleChangeRequestForm(user=user)

  try:
    form.clean()
  except Exception as ex:
    pytest.fail(f'Unexpected Error: {ex}')

@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
def test_invalid_clean_method_of_role_change_request_form(mocker):
  mocker.patch('account.models.RoleApproval.has_request_permission', return_value=False)
  user = factories.UserFactory()
  form = forms.RoleChangeRequestForm(user=user)

  with pytest.raises(ValidationError) as ex:
    form.clean()

  assert 'Your request has already registered.' in str(ex.value.args)

@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'commit',
  'count',
], [
  (False, 0),
  (True, 1),
], ids=[
  'do-not-save',
  'do-save',
])
def test_check_save_method_of_role_change_request_form(mocker, commit, count):
  ra_mock = mocker.patch('account.models.RoleApproval.update_record', return_value=None)
  user = factories.UserFactory()
  form = forms.RoleChangeRequestForm(user=user)
  form.save(commit=commit)

  assert ra_mock.call_count == count


# ====================
# = RoleApprovalForm =
# ====================
@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'params',
], [
  ({'is_approve': True}, ),
  ({'is_approve': False}, ),
  ({}, ),
], ids=[
  'is-approve',
  'is-not-approve',
  'not-set',
])
def test_check_validation_of_role_approval_form(params):
  user = factories.UserFactory(role=models.RoleType.MANAGER)
  form = forms.RoleApprovalForm(user=user, data=params)

  assert form.is_valid()

@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'role',
], [
  (models.RoleType.GUEST, ),
  (models.RoleType.CREATOR, ),
], ids=[
  'is-guest',
  'is-creator',
])
def test_invalid_arguments_of_clean_method_in_role_approval_form(mocker, role):
  user = factories.UserFactory(role=role)
  form = forms.RoleApprovalForm(user=user)

  with pytest.raises(ValidationError) as ex:
    form.clean()

  assert "You don’t have permission to update this record." in str(ex.value.args)

@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'is_approve',
  'call_counts',
  'record_counts',
], [
  (True,  1, 1),
  (False, 0, 0),
], ids=[
  'is-approve',
  'is-not-approve',
])
def test_check_approval_process_of_role_approval_form(mocker, is_approve, call_counts, record_counts):
  params = {
    'is_approve': is_approve,
  }
  instance = factories.RoleApprovalFactory(user=factories.UserFactory())
  manager = factories.UserFactory(role=models.RoleType.MANAGER)
  form = forms.RoleApprovalForm(user=manager, data=params, instance=instance)
  ra_mock = mocker.patch('account.models.RoleApproval.update_record', return_value=None)
  is_valid = form.is_valid()
  form.approval_process()

  assert is_valid
  assert ra_mock.call_count == call_counts
  assert models.RoleApproval.objects.all().count() == record_counts

# ==============
# = FriendForm =
# ==============
@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'number_of_friends',
], [
  (0, ),
  (1, ),
  (2, ),
], ids=[
  'no-friends',
  'best-friend',
  'manay-friends',
])
def test_validate_inputs_of_friend_form(number_of_friends):
  friends = list(factories.UserFactory.create_batch(number_of_friends, is_active=True)) if number_of_friends > 0 else []
  user = factories.UserFactory()
  params = {
    'friends': friends,
  }
  form = forms.FriendForm(user=user, data=params)

  assert form.is_valid()

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'user_type',
], [
  ('superuser', ),
  ('manager', ),
  ('myself', ),
], ids=lambda xs: str(xs))
def test_add_invalid_user_in_friend_form(user_type):
  user = factories.UserFactory(is_active=True)
  patterns = {
    'superuser': factories.UserFactory(is_active=True, is_staff=True, is_superuser=True),
    'manager': factories.UserFactory(is_active=True, role=models.RoleType.MANAGER),
    'myself': user,
  }
  invalid_user = patterns[user_type]
  friends = list(factories.UserFactory.create_batch(2, is_active=True)) + [invalid_user]
  params = {
    'friends': friends,
  }
  form = forms.FriendForm(user=user, data=params)
  is_valid = form.is_valid()
  err_msg = 'Select a valid choice. {} is not one of the available choices.'.format(invalid_user.pk)

  assert not is_valid
  assert err_msg in str(form.errors)

@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'friends_indices',
  'is_valid',
  'err_msg',
], [
  # members: 2, 3
  (   [      2, 3, 4], True, ''),
  (   [0,    2,    4], False, 'You need to select relevant friends because the individual group &quot;hoge&quot; has D member(s).'),
], ids=[
  'can-remove-friends',
  'cannot-remove-friends',
])
def test_validate_clean_friends_method_of_friend_form(friends_indices, is_valid, err_msg):
  # Index:  0    1    2    3    4
  names = ['A', 'B', 'C', 'D', 'E']
  friends = [factories.UserFactory(screen_name=name, is_active=True) for name in names]
  user = factories.UserFactory(is_active=True, friends=friends)
  _ = factories.IndividualGroupFactory(owner=user, name='hoge', members=[friends[2], friends[3]])
  new_friends = [friends[idx] for idx in friends_indices]
  params = {
    'friends': new_friends,
  }
  form = forms.FriendForm(user=user, data=params)
  out = form.is_valid()

  assert out == is_valid
  assert err_msg in str(form.errors)

@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'number_of_friends',
], [
  (0, ),
  (1, ),
  (2, ),
], ids=[
  'no-friends',
  'best-friend',
  'manay-friends',
])
def test_check_options_of_friend_form(number_of_friends):
  friends = list(factories.UserFactory.create_batch(number_of_friends, is_active=True)) if number_of_friends > 0 else []
  _ = factories.UserFactory.create_batch(4, is_active=True)
  user = factories.UserFactory(friends=friends)
  ids_of_friends = list(map(lambda val: val.pk, friends)) + [user.pk]
  others = UserModel.objects.collect_valid_normal_users().exclude(pk__in=ids_of_friends)
  form = forms.FriendForm(user=user)
  str_options = form.get_options
  exacts_items = g_generate_item(friends, True) + g_generate_item(others, False)
  options = json.loads(str_options)

  assert isinstance(str_options, str)
  assert len(options) == len(exacts_items)
  assert g_compare_options(options, exacts_items)

# =======================
# = IndividualGroupForm =
# =======================
@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'name',
  'data_type',
  'is_valid',
], [
  (None, 'best-friend', False),
  ('test-group', 'no-friends', False),
  ('test-group', 'best-friend', True),
  ('test-group', 'manay-friends', True),
  ('test-group', 'include-other-friends', False),
], ids=[
  'name-is-not-set',
  'no-friends',
  'best-friend',
  'manay-friends',
  'include-other-friends',
])
def test_validate_inputs_of_individual_group_form(name, data_type, is_valid):
  friends = list(factories.UserFactory.create_batch(3, is_active=True))
  others = list(factories.UserFactory.create_batch(2, is_active=True))
  all_members = friends + others
  user = factories.UserFactory(friends=friends)
  # Define patterns
  patterns = {
    'no-friends': [],
    'best-friend': [friends[0]],
    'manay-friends':friends,
    'include-other-friends': all_members,
  }
  params = {
    'members': patterns[data_type],
  }
  if name is not None:
    params['name'] = name
  form = forms.IndividualGroupForm(user=user, data=params)

  assert form.is_valid() == is_valid

@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'data_type',
  'exists_instance',
], [
  ('no-friends', False),
  ('best-friend', True),
  ('best-friend', False),
  ('manay-friends', True),
  ('manay-friends', False),
], ids=lambda val: str(val).lower())
def test_check_options_of_individual_group_form(data_type, exists_instance):
  friends = list(factories.UserFactory.create_batch(3, is_active=True))
  others = list(factories.UserFactory.create_batch(2, is_active=True))
  all_members = friends + others
  # Define patterns
  patterns = {
    'no-friends': [],
    'best-friend': [friends[0]],
    'manay-friends': friends,
  }
  # Define instances
  user = factories.UserFactory(friends=patterns[data_type])
  instance = factories.IndividualGroupFactory(owner=user, members=[friends[0]]) if exists_instance else None
  expected = {
    'no-friends': [],
    'best-friend': g_generate_item([friends[0]], exists_instance),
    'manay-friends': (g_generate_item([friends[0]], True) + g_generate_item([friends[1], friends[2]], False)) if exists_instance else g_generate_item(friends, False),
  }
  params = {
    'name': 'test-group',
    'members': patterns[data_type],
  }
  exacts_items = expected[data_type]
  form = forms.IndividualGroupForm(user=user, data=params, instance=instance)
  str_options = form.get_options
  options = json.loads(str_options)

  assert isinstance(str_options, str)
  assert len(options) == len(exacts_items)
  assert g_compare_options(options, exacts_items)

@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
def test_check_default_options_in_individual_group_form():
  friends = list(factories.UserFactory.create_batch(3, is_active=True))
  # Define instances
  user = factories.UserFactory(friends=friends)
  form = forms.IndividualGroupForm(user=user)
  form.instance = None
  str_options = form.get_options
  exacts_items = g_generate_item(friends, False)
  options = json.loads(str_options)

  assert isinstance(str_options, str)
  assert len(options) == len(exacts_items)
  assert g_compare_options(options, exacts_items)

@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
def test_check_clean_members_method_in_individual_group_form():
  user = factories.UserFactory()
  other = factories.UserFactory()
  params = {
    'name': 'hoge-group',
    'members': [other],
  }
  form = forms.IndividualGroupForm(user=user, data=params)
  form.cleaned_data = {'members': UserModel.objects.filter(pk__in=[other.pk])}

  with pytest.raises(ValidationError) as ex:
    form.clean_members()

  assert "Invalid member list. Some members are assigned except owner’s friends." in str(ex.value.args)