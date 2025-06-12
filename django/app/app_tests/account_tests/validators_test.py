import pytest
from django.core.exceptions import ValidationError
from account import validators

g_err_msg = 'Your password must contain at least four types which are an alphabet (uppercase/lowercase), a number, and a symbol.'

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
def test_valid_patterns(password):
  validator = validators.CustomPasswordValidator()
  validator.validate(password)

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
def test_invalid_patterns(password):
  validator = validators.CustomPasswordValidator()

  with pytest.raises(ValidationError) as ex:
    validator.validate(password)

  assert g_err_msg in ex.value.args

@pytest.mark.account
@pytest.mark.validator
def test_check_help_text_method():
  validator = validators.CustomPasswordValidator()
  out = validator.get_help_text()

  assert out == g_err_msg