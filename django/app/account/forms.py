from django import forms
from django.conf import settings
from django.core.signing import dumps
from django.contrib.auth import authenticate, get_user_model
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
from django.views.decorators.debug import sensitive_variables
from utils.models import (
  generate_default_filename,
  get_digest,
  DualListbox,
)
from utils.forms import (
  BaseFormWithCSS,
  ModelFormBasedOnUser,
)
from utils.widgets import CustomSwitchInput
from .validators import CustomDigestValidator
from . import models

UserModel = get_user_model()

##
# @brief Get forwarding port number
# @return port Port number or empty string
def _get_forwarding_port():
  val = getattr(settings, 'NGINX_FORWARDING_PORT', '')
  port = f':{val}' if val else ''

  return port

class LoginForm(AuthenticationForm, BaseFormWithCSS):
  username = forms.EmailField(
    label=gettext_lazy('Email address'),
    required=False,
    widget=forms.EmailInput(attrs={
      'autofocus': True,
      'autocomplete': 'username webauthn',
    }),
  )
  password = forms.CharField(
    label=gettext_lazy('Password'),
    required=False,
    strip=False,
    widget=forms.PasswordInput(attrs={
      'autocomplete': 'current-password',
    }),
  )
  passkeys = forms.CharField(
    label=gettext_lazy('Passkey'),
    required=False,
    widget=forms.HiddenInput(attrs={
      'id': 'passkeys',
      'name': 'passkeys',
    }),
  )

  ##
  # @brief Check whether the given user has `is_staff` permission or not.
  # @exception ValidationError The given user has `is_staff` permission.
  def confirm_login_allowed(self, user):
    super().confirm_login_allowed(user)

    if user.is_staff:
      raise forms.ValidationError(
        gettext_lazy('The given user who has staff permission cannot login.'),
        code='invalid_login',
      )

  ##
  # @breif Check input parameters
  # @return cleaned_data Valid field parameters
  @sensitive_variables()
  def clean(self):
    username = self.cleaned_data.get('username', '')
    password = self.cleaned_data.get('password', '')
    # Authentication with backend
    self.user_cache = authenticate(self.request, username=username, password=password)
    # Check authenticated result
    if self.user_cache is None:
      raise self.get_invalid_login_error()
    else:
      self.confirm_login_allowed(self.user_cache)

    return self.cleaned_data

##
# @brief Validate input digest
# @exception ValidationError if input digest does not match exact one
def _validate_hash_sign(value):
  exact_digest = get_digest()
  instance = CustomDigestValidator(exact_digest)
  instance.validate(value)

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
    validators=[_validate_hash_sign],
    help_text=gettext_lazy("Enter the today’s hash value."),
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
    port = _get_forwarding_port()
    context = {
      'protocol': req.scheme,
      'domain': f'{site_url.domain}{port}',
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
    widgets = {
      'screen_name': forms.TextInput(attrs={
        'autofocus': True,
      }),
    }

class CustomPasswordChangeForm(PasswordChangeForm, BaseFormWithCSS):
  ##
  # @brief Check data
  # @exception ValidationError The new password is same as old password
  def clean(self):
    old_password = self.cleaned_data.get('old_password')
    new_password = self.cleaned_data.get('new_password1')

    if old_password == new_password:
      raise forms.ValidationError(
        gettext_lazy('The old password is same as new password. Please enter difference passwords.'),
        code='same_passwords',
      )

    return super().clean()

class CustomPasswordResetForm(PasswordResetForm, BaseFormWithCSS):
  email = forms.EmailField(
    label=gettext_lazy('Email'),
    max_length=128,
    widget=forms.EmailInput(attrs={
      'autocomplete': 'email',
      'autofocus': True,
    }),
  )

  ##
  # @brief Check whether the given email address is registered or not
  def clean_email(self):
    email = self.cleaned_data.get('email')
    user_exists = UserModel.objects.filter(email=email, is_active=True).exists()

    if not user_exists:
      raise forms.ValidationError(
        gettext_lazy('The given email address is not registered or not enabled. Please check your email address.'),
        code='invalid_email',
      )

    return email

  ##
  # @brief Send email based on input parameters
  # @param kwargs Named arguments
  def save(self, **kwargs):
    req = kwargs.get('request')
    site_url = get_current_site(req)
    port = _get_forwarding_port()
    domain = f'{site_url.domain}{port}'

    super().save(domain_override=domain, **kwargs)

class CustomSetPasswordForm(SetPasswordForm, BaseFormWithCSS):
  class Meta:
    widgets = {
      'new_password1': forms.PasswordInput(attrs={
        'autocomplete': 'new-password',
        'autofocus': True,
      }),
    }

class CreatorDownloadForm(BaseFormWithCSS):
  class Meta:
    model = UserModel
    fields = []

  filename = forms.CharField(
    label=gettext_lazy('CSV filename'),
    max_length=128,
    required=True,
    widget=forms.TextInput(attrs={
      'class': 'form-control',
      'autofocus': True,
    }),
    help_text=gettext_lazy('You don’t have to enter the extention.'),
  )

  ##
  # @brief Constructor of GenreDownloadForm
  # @param args Positional arguments
  # @param kwargs Named arguments
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['filename'].initial = generate_default_filename()

  ##
  # @brief Create response data
  # @return kwargs Dictionary data
  def create_response_kwargs(self):
    filename = self.cleaned_data.get('filename', '').replace('.csv', '')
    # Check filename
    if not filename:
      filename = generate_default_filename()
    kwargs = UserModel.get_response_kwargs(filename)

    return kwargs

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
  # @param commit Describe whether the record is committed or not (Default: True)
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

  ##
  # @brief Check data
  # @exception ValidationError User does not have manager role
  def clean(self):
    is_valid = self.user.has_manager_role()

    if not is_valid:
      raise forms.ValidationError(
        gettext_lazy("You don’t have permission to update this record."),
        code='no_permission',
      )

  ##
  # @brief Conduct approval process
  def approval_process(self):
    instance = super().save(commit=False)
    is_approve = self.cleaned_data.get('is_approve')

    # In the case of that the request is accepted
    if is_approve:
      instance.update_record(self.user)
    # In the case of that the request is rejected
    else:
      instance.delete()

class FriendForm(forms.ModelForm):
  dual_listbox_template_name = 'renderer/custom_dual_listbox_preprocess.html'

  class Meta:
    model = UserModel
    fields = ('friends',)
    widgets = {
      'friends': forms.SelectMultiple(attrs={
        'class': 'custom-multi-selectbox',
      }),
    }

  ##
  # @brief Constructor of RoleApprovalForm
  # @param user Instance of access user
  # @param args Positional arguments
  # @param kwargs Named arguments
  def __init__(self, user, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.user = user
    self.fields['friends'].queryset = UserModel.objects.collect_valid_normal_users(self.user)
    self.dual_listbox = DualListbox()

  ##
  # @brief Get options of select element
  # @return options JSON data of option element which consists of primary-key, label-name, and selected-or-not
  @property
  def get_options(self):
    all_users = self.fields['friends'].queryset
    selected_friends = self.user.friends.all()
    callback = self.dual_listbox.user_cb
    options = self.dual_listbox.collect_options_of_items(all_users, selected_friends, callback)

    return options

  ##
  # @brief Check friends list
  # @exception ValidationError Some individual groups include deleted firends
  # @exception ValidationError There are some users who have manager role
  def clean_friends(self):
    friends = self.cleaned_data.get('friends')

    # Check whether the friends are included into each individual group or not.
    for group in self.user.group_owners.all():
      rest_friends = group.extract_invalid_friends(friends).order_by('pk')

      if rest_friends.exists():
        names = [str(friend) for friend in rest_friends]

        raise forms.ValidationError(
          gettext_lazy('You need to select relevant friends because the individual group "%(group)s" has %(friends)s member(s).'),
          code='invalid_friends',
          params={'group': str(group), 'friends': ','.join(names)},
        )

    return friends

class IndividualGroupForm(ModelFormBasedOnUser):
  dual_listbox_template_name = 'renderer/custom_dual_listbox_preprocess.html'
  owner_name = 'owner'

  class Meta:
    model = models.IndividualGroup
    fields = ('name', 'members')
    widgets = {
      'name': forms.TextInput(attrs={
        'class': 'form-control',
        'autofocus': True,
      }),
      'members': forms.SelectMultiple(attrs={
        'class': 'custom-multi-selectbox',
      }),
    }

  def __init__(self, user, *args, **kwargs):
    super().__init__(*args, user=user, **kwargs)
    self.fields['members'].queryset = self.user.friends.all()
    self.fields['members'].required = False
    self.dual_listbox = DualListbox()

  ##
  # @brief Get options of select element
  # @return options JSON data of option element which consists of primary-key, label-name, and selected-or-not
  @property
  def get_options(self):
    friends = self.user.friends.all()
    members = self.instance.members.all() if self.instance else None
    callback = self.dual_listbox.user_cb
    options = self.dual_listbox.collect_options_of_items(friends, members, callback)

    return options

  ##
  # @brief Check `members` data
  # @exception ValidationError There are no members in the request data
  def clean_members(self):
    members = self.cleaned_data.get('members')
    # Check input members
    if not members:
      raise forms.ValidationError(
        gettext_lazy('This field is required.'),
        code='invalid_request',
      )
    # Check the constituent members
    if self._meta.model.exists_invalid_members(members, self.user.friends):
      raise forms.ValidationError(
        gettext_lazy("Invalid member list. Some members are assigned except owner’s friends."),
        code='invalid_members',
      )

    return members

  ##
  # @brief Update friends column in UserModel
  # @param instance Instance of UserModel
  # @param args Positional arguments
  # @param kwargs Named arguments
  def post_process(self, instance, *args, **kwargs):
    super().post_process(instance, *args, **kwargs)
    self.save_m2m()