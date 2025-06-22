from django.core.exceptions import ValidationError
from django.core.signing import BadSignature, SignatureExpired, loads
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy
import re

UserModel = get_user_model()

class CustomPasswordValidator:
  ##
  # @brief Constructor of CustomPasswordValidator
  def __init__(self):
    self.patterns = [
      re.compile(reg_exp)
      for reg_exp in [r"(?=.*\d)", r"(?=.*[a-z])", r"(?=.*[A-Z])", r"(?=.*[~!@#$%^&*_\-+=`|(){}\[\]:;\"\'<>,.?/])"]
    ]

  ##
  # @brief Validate input password
  # @param password Target password
  # @param user User instance (default is None)
  # @exception ValidationError Input password is invalid
  def validate(self, password, user=None):
    is_valid = all([pattern.match(password) for pattern in self.patterns])

    if not is_valid:
      raise ValidationError(
        self.get_help_text(),
        code='invalid_password',
      )

  ##
  # @brief Get constraint message
  # @return Constraint message
  def get_help_text(self):
    return gettext_lazy('Your password must contain at least four types which are an alphabet (uppercase/lowercase), a number, and a symbol.')

class CustomDigestValidator:
  ##
  # @brief Constructor of CustomDigestValidator
  def __init__(self, digest):
    self._digest = digest

  ##
  # @brief Validate input digest
  # @param value message digest
  # @param kwargs named arguments
  # @exception ValidationError Input digest is invalid
  def validate(self, value, **kwargs):
    is_valid = self._digest == value

    if not is_valid:
      raise ValidationError(
        self.get_help_text(),
        code='invalid_digest',
      )

  ##
  # @brief Get constraint message
  # @return Constraint message
  def get_help_text(self):
    return gettext_lazy('Invalid a digest value.')

class CustomRegistrationTokenValidator:
  ##
  # @brief Constructor of CustomRegistrationTokenValidator
  def __init__(self, timeout_seconds):
    self._max_age = timeout_seconds
    self._instance = None

  ##
  # @brief Validate input token
  # @param token Target token
  # @exception ValidationError Input token is invalid
  def validate(self, token):
    is_valid = True

    try:
      user_pk = loads(token, max_age=self._max_age)
    except (SignatureExpired, BadSignature):
      is_valid = False
    else:
      try:
        user = UserModel.objects.get(pk=user_pk)
      except UserModel.DoesNotExist:
        is_valid = False
      else:
        if user.is_active:
          is_valid = False
        else:
          self._instance = user

    if not is_valid:
      raise ValidationError(
        gettext_lazy('Invalid token.'),
        code='invalid_token',
      )

  ##
  # @brief Get instance
  # @pre The `validate` method has already called
  # @return Instance of User model with relevant to validated token
  def get_instance(self):
    return self._instance