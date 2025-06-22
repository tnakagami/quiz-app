from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import (
  LoginView,
  LogoutView,
  PasswordChangeView,
  PasswordChangeDoneView,
  PasswordResetView,
  PasswordResetDoneView,
  PasswordResetConfirmView,
  PasswordResetCompleteView,
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.views.generic import (
  TemplateView,
  ListView,
  CreateView,
  UpdateView,
  DetailView,
)
from utils.views import (
  IsOwner,
  HasManagerRole,
  BaseCreateUpdateView,
  CustomDeleteView,
  Index,
  DjangoBreadcrumbsMixin,
)
from . import models, forms, validators

UserModel = get_user_model()

##
# @brief Get timelimit of definitive registration as second units
# @return timelimit Timelimit (sec)
def _get_timelimit_seconds():
  timelimit = getattr(settings, 'ACTIVATION_TIMEOUT_SECONDS', 5*60)

  return timelimit

##
# @brief Get timelimit of definitive registration as minute units
# @return timelimit Timelimit (min)
def _get_timelimit_minutes():
  timeout_sec = _get_timelimit_seconds()
  timelimit = timeout_sec // 60

  return timelimit

##
# @brief Get timeout of password reset as minute units
# @return timeout timeout (min)
def _get_password_reset_timeout_minutes():
  timeout = settings.PASSWORD_RESET_TIMEOUT // 60

  return timeout

class LoginPage(LoginView, DjangoBreadcrumbsMixin):
  redirect_authenticated_user = True
  form_class = forms.LoginForm
  template_name = 'account/login.html'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:login',
    title=gettext_lazy('Login'),
    parent_view_class=Index,
  )

class LogoutPage(LogoutView):
  template_name = 'index.html'

# ================
# = User profile =
# ================
class IsPrivate(UserPassesTestMixin):
  ##
  # @brief Check whether request user can access to target page or not
  # @return bool Judgement result
  # @retval True Request user can access to the page
  # @retval False Request user can access to the page except superuser
  def test_func(self):
    user = self.request.user
    pk = self.kwargs.get('pk')
    is_valid = str(pk) == str(user.pk) or user.is_superuser

    return is_valid

class UserProfilePage(LoginRequiredMixin, IsPrivate, DetailView, DjangoBreadcrumbsMixin):
  raise_exception = True
  model = UserModel
  template_name = 'account/profiles/user_profile.html'
  context_object_name = 'owner'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:user_profile',
    title=gettext_lazy('User profile'),
    parent_view_class=Index,
    url_keys=['pk'],
  )

class UpdateUserProfilePage(LoginRequiredMixin, IsPrivate, UpdateView, DjangoBreadcrumbsMixin):
  raise_exception = True
  model = UserModel
  form_class = forms.UserProfileForm
  template_name = 'account/profiles/profile_form.html'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:update_profile',
    title=gettext_lazy('Update user profile'),
    parent_view_class=UserProfilePage,
    url_keys=['pk'],
  )

  ##
  # @brief Get the URL to come back to the previous page
  # @return Target URL
  def get_success_url(self):
    return reverse('account:user_profile', kwargs={'pk': self.kwargs['pk']})

class IsNotAuthenticated(UserPassesTestMixin):
  ##
  # @brief Check whether request user can access to target page or not
  # @return bool Judgement result
  # @retval True Request user can access to the page
  # @retval False Request user can access to the page except superuser
  def test_func(self):
    return not self.request.user.is_authenticated

class CreateAccountPage(IsNotAuthenticated, CreateView, DjangoBreadcrumbsMixin):
  raise_exception = True
  form_class = forms.UserCreationForm
  template_name = 'account/create_account.html'
  subject_template_name = 'account/mail_template/provisional_registration/subject.txt'
  email_template_name = 'account/mail_template/provisional_registration/message.txt'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:create_account',
    title=gettext_lazy('Create account'),
    parent_view_class=Index,
  )

  ##
  # @brief Process tasks after form validation
  # @param form Instance of `form_class`
  # @return response Instance of Django's response
  def form_valid(self, form):
    user = form.save()
    config = {
      'timelimit': _get_timelimit_minutes(),
      'subject_template_name': self.subject_template_name,
      'email_template_name': self.email_template_name,
      'user': user,
    }
    form.send_email(self.request, config)
    response = redirect('account:done_account_creation')

    return response

class DoneAccountCreationPage(IsNotAuthenticated, TemplateView, DjangoBreadcrumbsMixin):
  template_name = 'account/done_account_creation.html'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:done_account_creation',
    title=gettext_lazy('Conducted provisional registration'),
    parent_view_class=Index,
  )

  ##
  # @brief Get context data
  # @param kwargs named arguments
  # @return context context which is used in template file
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    timelimit = _get_timelimit_minutes()
    context['warning_message'] = gettext_lazy('In addition, URL is valid for %(timelimit)s minutes.' % {'timelimit': timelimit})

    return context

class CompleteAccountCreationPage(IsNotAuthenticated, TemplateView):
  template_name = 'account/complete_account_creation.html'

  ##
  # @brief Process GET request
  # @param request Django's request instance
  # @param kwargs named arguments
  # @return response Django's response instance
  def get(self, request, **kwargs):
    timeout_seconds = _get_timelimit_seconds()
    validator = validators.CustomRegistrationTokenValidator(timeout_seconds)
    token = kwargs.get('token')

    try:
      validator.validate(token)
    except ValidationError:
      response = HttpResponseBadRequest()
    else:
      user = validator.get_instance()
      user.activation()
      login(request, user)
      response = super().get(request, **kwargs)

    return response

class ChangePasswordPage(LoginRequiredMixin, PasswordChangeView, DjangoBreadcrumbsMixin):
  raise_exception = True
  form_class = forms.CustomPasswordChangeForm
  template_name = 'account/passwords/password_change_form.html'
  success_url = reverse_lazy('account:done_password_change')
  crumbles_context_attribute = 'owner'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:update_password',
    title=gettext_lazy('Update password'),
    parent_view_class=UserProfilePage,
  )

  ##
  # @brief Get context data
  # @param kwargs named arguments
  # @return context context which is used in template file
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    self.owner = self.request.user

    return context

class DonePasswordChangePage(LoginRequiredMixin, PasswordChangeView, DjangoBreadcrumbsMixin):
  raise_exception = True
  template_name = 'account/passwords/done_password_change.html'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:done_password_change',
    title=gettext_lazy('Password was updated'),
    parent_view_class=Index,
  )

class ResetPasswordPage(IsNotAuthenticated, PasswordResetView, DjangoBreadcrumbsMixin):
  raise_exception = True
  form_class = forms.CustomPasswordResetForm
  template_name = 'account/passwords/password_reset_form.html'
  subject_template_name = 'account/mail_template/password_reset/subject.txt'
  email_template_name = 'account/mail_template/password_reset/message.txt'
  extra_email_context = {'timelimit': _get_password_reset_timeout_minutes()}
  success_url = reverse_lazy('account:done_password_reset')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:reset_password',
    title=gettext_lazy('Reset password'),
    parent_view_class=LoginPage,
  )

class DonePasswordResetPage(IsNotAuthenticated, PasswordResetDoneView, DjangoBreadcrumbsMixin):
  raise_exception = True
  template_name = 'account/passwords/done_password_reset.html'

  ##
  # @brief Get context data
  # @param kwargs named arguments
  # @return context context which is used in template file
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    timelimit = _get_password_reset_timeout_minutes()
    context['warning_message'] = gettext_lazy('In addition, URL is valid for %(timelimit)s minutes.' % {'timelimit': timelimit})

    return context

class ConfirmPasswordResetPage(IsNotAuthenticated, PasswordResetConfirmView):
  raise_exception = True
  form_class = forms.CustomSetPasswordForm
  template_name = 'account/passwords/confirm_password_form.html'
  success_url = reverse_lazy('account:complete_password_reset')

class CompletePasswordResetPage(IsNotAuthenticated, PasswordResetCompleteView, DjangoBreadcrumbsMixin):
  raise_exception = True
  template_name = 'account/passwords/complete_password_reset.html'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:complete_password_reset',
    title=gettext_lazy('Password was reset'),
    parent_view_class=Index,
  )

# =============
# = User role =
# =============
class RoleChangeRequestListPage(LoginRequiredMixin, HasManagerRole, ListView, DjangoBreadcrumbsMixin):
  model = models.RoleApproval
  template_name = 'account/profiles/role_change_requests.html'
  paginate_by = 15
  context_object_name = 'role_change_reqs'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:role_change_requests',
    title=gettext_lazy('Role change requests'),
    parent_view_class=Index,
  )

  ##
  # @brief Get queryset
  # @return Queryset of role approval records
  def get_queryset(self):
    return self.model.objects.collect_targets()

  ##
  # @brief Get context data
  # @param kwargs named arguments
  # @return context context which is used in template file
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['form'] = forms.RoleApprovalForm(user=self.request.user)

    return context

class HasRequestPermission(UserPassesTestMixin):
  ##
  # @brief Check whether request user can access to target page or not
  # @return bool Judgement result
  # @retval True Request user can access to the page
  # @retval False Request user can access to the page except superuser
  def test_func(self):
    return models.RoleApproval.has_request_permission(self.request.user)

class CreateRoleChangeRequestPage(BaseCreateUpdateView, HasRequestPermission, CreateView, DjangoBreadcrumbsMixin):
  model = models.RoleApproval
  form_class = forms.RoleChangeRequestForm
  template_name = 'account/profiles/change_role_form.html'
  crumbles_context_attribute = 'owner'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:create_role_change_request',
    title=gettext_lazy('Change role'),
    parent_view_class=UserProfilePage,
  )

  ##
  # @brief Get context data
  # @param kwargs named arguments
  # @return context context which is used in template file
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    self.owner = self.request.user

    return context

  ##
  # @brief Get the URL to come back to the previous page
  # @return Target URL
  def get_success_url(self):
    return reverse('account:user_profile', kwargs={'pk': self.request.user.pk})

class UpdateRoleApproval(BaseCreateUpdateView, HasManagerRole, UpdateView):
  model = models.RoleApproval
  form_class = forms.RoleApprovalForm
  http_method_names = ['post']
  success_url = reverse_lazy('account:role_change_requests')

  ##
  # @brief Conduct post process when form data is valid
  # @param form Instance of form_class
  def form_valid(self, form):
    form.approval_process()

    return HttpResponseRedirect(self.get_success_url())

# ===========
# = Friends =
# ===========
class UpdateFriendPage(BaseCreateUpdateView, IsPrivate, UpdateView, DjangoBreadcrumbsMixin):
  model = UserModel
  form_class = forms.FriendForm
  template_name = 'account/profiles/friend_form.html'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:update_friend',
    title=gettext_lazy('Register/Unregister friends'),
    parent_view_class=UserProfilePage,
    url_keys=['pk'],
  )

  ##
  # @brief Get the URL to come back to the previous page
  # @return Target URL
  def get_success_url(self):
    return reverse('account:user_profile', kwargs={'pk': self.request.user.pk})

# ====================
# = Individual group =
# ====================
class IndividualGroupListPage(LoginRequiredMixin, ListView, DjangoBreadcrumbsMixin):
  model = models.IndividualGroup
  template_name = 'account/profiles/group_list.html'
  crumbles_context_attribute = 'owner'
  paginate_by = 15
  context_object_name = 'own_groups'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:individual_group_list',
    title=gettext_lazy('Individual groups'),
    parent_view_class=UserProfilePage,
  )

  ##
  # @brief Get queryset
  # @return Queryset of individual group
  def get_queryset(self):
    return self.request.user.group_owners.all()

  ##
  # @brief Get context data
  # @param kwargs named arguments
  # @return context context which is used in template file
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    self.owner = self.request.user

    return context

class CreateIndividualGroupPage(BaseCreateUpdateView, CreateView, DjangoBreadcrumbsMixin):
  model = models.IndividualGroup
  form_class = forms.IndividualGroupForm
  template_name = 'account/profiles/group_form.html'
  success_url = reverse_lazy('account:individual_group_list')
  crumbles_context_attribute = 'owner'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:create_group',
    title=gettext_lazy('Create/Update group'),
    parent_view_class=IndividualGroupListPage,
  )

  ##
  # @brief Get context data
  # @param kwargs named arguments
  # @return context context which is used in template file
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    self.owner = self.request.user

    return context

class UpdateIndividualGroupPage(BaseCreateUpdateView, IsOwner, UpdateView, DjangoBreadcrumbsMixin):
  owner_name = 'owner'
  model = models.IndividualGroup
  form_class = forms.IndividualGroupForm
  template_name = 'account/profiles/group_form.html'
  success_url = reverse_lazy('account:individual_group_list')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='account:update_group',
    title=gettext_lazy('Create/Update group'),
    parent_view_class=IndividualGroupListPage,
    url_keys=['pk'],
  )

class DeleteIndividualGroup(CustomDeleteView):
  owner_name = 'owner'
  model = models.IndividualGroup
  success_url = reverse_lazy('account:individual_group_list')