from django import forms
from django.core.signing import dumps
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
  AuthenticationForm,
  BaseUserCreationForm,
  PasswordChangeForm,
  PasswordResetForm,
  SetPasswordForm,
)
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy
from utils.forms import BaseFormWithCSS
from utils.widgets import CustomSwitchInput
from .validators import CustomDigestValidator
from . import models

UserModel = get_user_model()

class LoginForm(AuthenticationForm, BaseFormWithCSS):
  username = forms.EmailField(widget=forms.EmailInput(attrs={'autofocus': True}))

class UserCreationForm(BaseUserCreationForm, BaseFormWithCSS):
  class Meta:
    model = UserModel
    fields = ('email', 'screen_name')
    field_order = ('email', 'password1', 'password2', 'screen_name', 'hash_sign')
    field_classes = {
      'email': forms.EmailField,
      'screen_name': forms.CharField,
    }
    widgets = {
      'email': forms.EmailInput(attrs={'autofocus': True}),
      'screen_name': forms.TextInput(),
    }

  hash_sign = forms.CharField(
    label=gettext_lazy('Hash value'),
    required=True,
    widget=forms.TextInput(),
    validators=[CustomDigestValidator().validate],
    help_text=gettext_lazy("Enter the today's hash value."),
  )

  ##
  # @brief Delete an old account to avoid registering duplicated account if it exists
  def clean_email(self):
    email = self.cleaned_data.get('email')
    UserModel.objects.filter(email=email, is_active=False).delete()

    return email

  ##
  # @brief Save user instance without account activation
  # @return user Instance of User model
  def save(self):
    user = super().save(commit=False)
    user.is_active = False
    user.save()

    return user

  ##
  # @brief Send email to user to conduct account activation
  # @param req Django's request instance
  # @param config Dict object which includes timelimit, user instance, subject template name, and email template name
  def send_email(self, req, config):
    user = config['user']
    site_url = get_current_site(req)
    context = {
      'protocol': req.scheme,
      'domain': site_url.domain,
      'token': dumps(str(user.pk)),
      'user': user,
      'timelimit': config['timelimit'],
    }
    # Get messages
    subject = render_to_string(config['subject_template_name'], context)
    message = render_to_string(config['email_template_name'], context)
    user.email_user(''.join(subject.splitlines()), message)

class UserProfileForm(forms.ModelForm, BaseFormWithCSS):
  class Meta:
    model = UserModel
    fields = ('screen_name',)

class CustomPasswordChangeForm(PasswordChangeForm, BaseFormWithCSS):
  ##
  # @brief Check data
  # @exception ValidationError The new password is same as old password
  def clean(self):
    old_password = self.cleaned_data.get('old_password')
    new_password = self.cleaned_data.get('new_password1')

    if old_password == new_password:
      raise forms.ValidationError(
        gettext_lazy('The new password is same as new password. Please enter difference passwords.'),
        code='same_passwords',
      )

    return super().clean()

class CustomPasswordResetForm(PasswordResetForm, BaseFormWithCSS):
  email = forms.EmailField(
    label=gettext_lazy('Email'),
    max_length=128,
    widget=forms.EmailInput(attrs={'autocomplete': 'email'}),
  )

class CustomSetPasswordForm(SetPasswordForm, BaseFormWithCSS):
  pass

class RoleChangeRequestForm(forms.ModelForm, BaseFormWithCSS):
  class Meta:
    model = models.RoleApproval
    fields = []

  ##
  # @brief Constructor of RoleChangeRequestForm
  # @param user Instance of access user
  # @param args Positional arguments
  # @param kwargs Named arguments
  def __init__(self, user, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.user = user

  ##
  # @brief Check data
  # @exception ValidationError User's request is duplicated
  def clean(self):
    is_valid = models.RoleApproval.has_request_permission(self.user)

    if not is_valid:
      raise forms.ValidationError(
        gettext_lazy('Your request has already registered.'),
        code='duplicated_request',
      )

  ##
  # @brief Save instance
  # @pre User's role is either GUEST or MANAGER
  def save(self, commit=True):
    instance = super().save(commit=False)

    if commit:
      instance.update_record(self.user)

    return instance

class RoleApprovalForm(forms.ModelForm):
  class Meta:
    model = models.RoleApproval
    fields = []

  ##
  # @brief Constructor of RoleApprovalForm
  # @param user Instance of access user
  # @param args Positional arguments
  # @param kwargs Named arguments
  def __init__(self, user, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.user = user

  is_approve = forms.BooleanField(
    label=gettext_lazy('Approve or not'),
    widget=CustomSwitchInput(attrs={
      'id': 'approve-type',
      'class': 'form-check-input',
    }),
    required=False,
  )

  def clean(self):
    is_valid = self.user.has_manager_role()

    if not is_valid:
      raise forms.ValidationError(
        gettext_lazy("You don't have permission to update this record."),
        code='no_permission',
      )

  def approval_process(self):
    instance = super().save(commit=False)
    is_approve = self.cleaned_data.get('is_approve')

    # In the case of that the request is accepted
    if is_approve:
      instance.update_record(self.user)
    # In the case of that the request is rejected
    else:
      instance.delete()