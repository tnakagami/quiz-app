import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.urls import reverse
from app_tests import factories
from account import forms, models

UserModel = get_user_model()
g_complex_passwd = 'h2o$Jax3#1Pi'
g_wrong_password = 'h0o$jAx4#Pi5'

@pytest.mark.account
@pytest.mark.form
@pytest.mark.django_db
@pytest.mark.parametrize([
  'email',
  'password',
  'is_valid',
], [
  ('hoge@example.com', 'test-hoge2pass',  True),
  ('nobody@foo.com',   'test-hoge2pass',  False),
  ('hoge@example.com', 'wrong-pass2word', False),
  (              None, 'test-hoge2pass',  False),
  ('hoge@example.com',              None, False),
], ids=[
  'can-login',
  'invalid-email',
  'invalid-password',
  'email-is-empty',
  'password-is-empty',
])
def test_check_login_form(email, password, is_valid):
  raw_password = 'test-hoge2pass'
  user = factories.UserFactory(
    email='hoge@example.com',
    is_active=True,
  )
  user.set_password(raw_password)
  user.save()

  # Create form parameters
  params = {
    'username': email,
    'password': password,
  }
  form = forms.LoginForm(data=params)

  assert form.is_valid() == is_valid

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
def test_check_send_email_method_of_user_creation_form(mocker):
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
  exact_url = f'{fake_obj.scheme}://{fake_obj.domain}{relevant_link}'
  exact_timelimit = f'The above url is valid for 3 minutes'  # Based on "{'timelimit': 3,} in config"
  # Check whether this method is only called at once
  email_user_mock.assert_called_once()
  assert 'Quiz app - Account registration' in subject
  assert user.email in message
  assert exact_url in message
  assert exact_timelimit in message

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

  assert "You don't have permission to update this record." in str(ex.value.args)

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