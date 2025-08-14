from django import forms
from django.utils.translation import gettext_lazy
from . import models

class UserPasskeyForm(forms.ModelForm):
  template_name = 'renderer/custom_form.html'

  class Meta:
    model = models.UserPasskey
    fields = []

  ##
  # @brief Toggle target passkey
  # @param commit Commit flag (True: update instance, False: Do not update instance)
  # @return instance Instance of UserPasskey model
  def save(self, commit=True):
    instance = super().save(commit=False)
    instance.is_enabled = not instance.is_enabled

    if commit:
      instance.save()

    return instance