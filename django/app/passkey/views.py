from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils.translation import gettext_lazy
from django.urls import reverse_lazy
from django.views.generic import (
  View,
  ListView,
  CreateView,
  UpdateView,
)
from utils.views import (
  CanUpdate,
  CustomDeleteView,
  DjangoBreadcrumbsMixin,
)
from account.views import UserProfilePage
from . import models, forms

class PasskeyListPage(LoginRequiredMixin, ListView, DjangoBreadcrumbsMixin):
  model = models.UserPasskey
  template_name = 'passkey/passkey_list.html'
  paginate_by = 50
  context_object_name = 'passkeys'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='passkey:passkey_list',
    title=gettext_lazy('Passkey list'),
    parent_view_class=UserProfilePage,
  )

  ##
  # @brief Get queryset
  # @return queryset Fitered queryset
  def get_queryset(self):
    return self.request.user.passkeys.all()

class UpdatePasskeyPage(LoginRequiredMixin, CanUpdate, UpdateView):
  raise_exception = True
  http_method_names = ['post']
  model = models.UserPasskey
  form_class = forms.UserPasskeyForm
  success_url = reverse_lazy('passkey:passkey_list')

class DeletePasskey(CustomDeleteView):
  model = models.UserPasskey
  success_url = reverse_lazy('passkey:passkey_list')

class RegisterPasskey(LoginRequiredMixin, View):
  raise_exception = True
  http_method_names = ['get']

  ##
  # @brief Process GET method requested by ajax function
  # @param request Instance of HttpRequest
  # @param args Positional arguments
  # @param kwargs Named arguments
  # @return response Instance of JsonResponse
  def get(self, request, *args, **kwargs):
    instance = models.UserPasskey(user=request.user)
    data = instance.register_begin(request)
    response = JsonResponse(dict(data), json_dumps_params={'ensure_ascii': False})

    return response

class CompletePasskeyRegistration(LoginRequiredMixin, View):
  raise_exception = True
  http_method_names = ['post']

  ##
  # @brief Process POST method requested by ajax function
  # @param request Instance of HttpRequest
  # @param args Positional arguments
  # @param kwargs Named arguments
  # @return response Instance of JsonResponse
  def post(self, request, *args, **kwargs):
    instance = models.UserPasskey(user=request.user)
    status = instance.register_complete(request)
    response = JsonResponse(dict(status), json_dumps_params={'ensure_ascii': False}, status=status['code'])

    return response

class BeginPasskeyAuthentication(View):
  raise_exception = True
  http_method_names = ['get']

  ##
  # @brief Process GET method requested by ajax function
  # @param request Instance of HttpRequest
  # @param args Positional arguments
  # @param kwargs Named arguments
  # @return response Instance of JsonResponse
  def get(self, request, *args, **kwargs):
    data = models.UserPasskey.auth_begin(request)
    response = JsonResponse(dict(data), json_dumps_params={'ensure_ascii': False})

    return response