from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy
import re

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