import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.core.signing import BadSignature, SignatureExpired
from app_tests import factories
from account import validators

UserModel = get_user_model()
g_err_msg = 'Your password must contain at least four types which are an alphabet (uppercase/lowercase), a number, and a symbol.'

# ===========================
# = CustomPasswordValidator =
# ===========================
@pytest.mark.account
@pytest.mark.validator
@pytest.mark.parametrize([
  'password',
], [
  ('0aZ~',), ('1bY!',), ('2cX@',), ('3dW#',), ('4eV$',), ('5fU%',), ('6gT^',), ('7hS&',), ('8iR*',), ('9jQ_',),
  ('0kP-',), ('1lO+',), ('2mN=',), ('3nM`',), ('4oL|',), ('5pK(',), ('6qJ)',), ('7rI{',), ('8sH}',), ('9tG[',),
  ('0uF]',), ('1vE:',), ('2wD;',), ('3xC"',), ("4yB'",), ('5zA<',), ('6aZ>',), ('7aZ,',), ('8aZ.',), ('9aZ?',),
  ('0aZ/',),
], ids=lambda vals: vals[-2:])
def test_valid_patterns_of_password_validator(password):
  validator = validators.CustomPasswordValidator()

  try:
    validator.validate(password)
  except Exception as ex:
    pytest.fail(f'Unexpected Error: {ex}')

@pytest.mark.account
@pytest.mark.validator
@pytest.mark.parametrize([
  'password',
], [
  ('123',   ), ('abc',   ), ('XYZ',   ), ('@+!',),
  ('123abc',), ('123XYZ',), ('123@+!',),
  ('abcXYZ',), ('abc@+!',),
  ('XYZ@+!',),
  ('abcXYZ@+!',),
  ('123XYZ@+!',),
  ('123abc@+!',),
  ('123abcXYZ',),
], ids=[
  'only-numbers',
  'only-lowercase-alphabets',
  'only-uppercase-alphabets',
  'only-symbols',
  'numbers-lowercase-alphabets',
  'numbers-uppercase-alphabets',
  'numbers-symbols',
  'lowercase-alphabets-uppercase-alphabets',
  'lowercase-alphabets-symbols',
  'uppercase-alphabets-symbols',
  'no-numbers',
  'no-lowercase-alphabets',
  'no-uppercase-alphabets',
  'no-symbols',
])
def test_invalid_patterns_of_password_validator(password):
  validator = validators.CustomPasswordValidator()

  with pytest.raises(ValidationError) as ex:
    validator.validate(password)

  assert g_err_msg in ex.value.args

@pytest.mark.account
@pytest.mark.validator
def test_check_help_text_method_of_password_validator():
  validator = validators.CustomPasswordValidator()
  out = validator.get_help_text()

  assert out == g_err_msg

# =========================
# = CustomDigestValidator =
# =========================
@pytest.mark.account
@pytest.mark.validator
def test_check_valid_digest_of_digest_validator():
  exact_val = 'abc123'
  validator = validators.CustomDigestValidator(exact_val)

  try:
    validator.validate(exact_val)
  except Exception as ex:
    pytest.fail(f'Unexpected Error: {ex}')

@pytest.mark.account
@pytest.mark.validator
def test_check_invalid_digest_of_digest_validator():
  validator = validators.CustomDigestValidator('abc123')
  err_msg = 'Invalid a digest value.'

  with pytest.raises(ValidationError) as ex:
    validator.validate('xyz')

  assert err_msg in ex.value.args
  assert err_msg == validator.get_help_text()

# ====================================
# = CustomRegistrationTokenValidator =
# ====================================
@pytest.mark.account
@pytest.mark.validator
@pytest.mark.django_db
def test_check_valid_token_of_token_validator(mocker):
  instance = factories.UserFactory(is_active=False)
  mocker.patch('account.validators.loads', return_value=instance.pk)
  validator = validators.CustomRegistrationTokenValidator(0)

  try:
    validator.validate(None)
  except Exception as ex:
    pytest.fail('Unexpected error: {ex}')

  # Get instance
  user = validator.get_instance()

  assert isinstance(user, UserModel)
  assert not user.is_active

@pytest.mark.account
@pytest.mark.validator
@pytest.mark.parametrize([
  'config_indices',
], [
  ([0],),
  ([1],),
  ([2, 3],),
  ([2, 4],),
], ids=[
  'invalid-signature',
  'signature-is-expired',
  'user-does-not-exist',
  'user-has-already-activated',
])
def test_invalid_token_of_token_validator(mocker, config_indices):
  class DummyUser:
    is_active = True

  target_config_list = [
    {
      'target': 'account.validators.loads',
      'config': {'side_effect': BadSignature()},
    },
    {
      'target': 'account.validators.loads',
      'config': {'side_effect': SignatureExpired()},
    },
    {
      'target': 'account.validators.loads',
      'config': {'return_value': 0},
    },
    {
      'target': 'account.validators.UserModel.objects.get',
      'config': {'side_effect': UserModel.DoesNotExist()},
    },
    {
      'target': 'account.validators.UserModel.objects.get',
      'config': {'return_value': DummyUser()},
    },
  ]

  for idx in config_indices:
    element = target_config_list[idx]
    mocker.patch(element['target'], **element['config'])

  validator = validators.CustomRegistrationTokenValidator(0)

  with pytest.raises(ValidationError) as ex:
    validator.validate(None)

  # Get instance
  user = validator.get_instance()

  assert 'Invalid token' in ex.value.args[0]
  assert user is None