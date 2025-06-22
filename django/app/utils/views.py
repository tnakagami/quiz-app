from django.urls import reverse
from django.utils.translation import gettext_lazy
from django.views.generic import TemplateView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from crumbles import CrumblesViewMixin, CrumbleDefinition
from operator import attrgetter, methodcaller
from .models import get_digest

class IsOwner(UserPassesTestMixin):
  owner_name = 'user'

  ##
  # @brief Check whether request user can access to target page or not
  # @return bool Judgement result
  # @retval True Request user can access to the page
  # @retval False Request user can access to the page except superuser
  def test_func(self):
    try:
      # Get target instance
      instance = self.get_object()
      # Get owner
      owner = getattr(instance, self.owner_name, instance)
      # Judge whether the access is valid or not.
      user = self.request.user
      is_valid = owner.pk == user.pk or user.is_superuser
    except:
      is_valid = False

    return is_valid

class IsGuest(UserPassesTestMixin):
  ##
  # @brief Check whether request user can access to target page or not
  # @return bool Judgement result
  # @retval True Request user can access to the page
  # @retval False Request user can access to the page except superuser
  def test_func(self):
    return self.request.user.is_guest()

class HasManagerRole(UserPassesTestMixin):
  ##
  # @brief Check whether request user can access to target page or not
  # @return bool Judgement result
  # @retval True Request user can access to the page
  # @retval False Request user can access to the page except superuser
  def test_func(self):
    return self.request.user.has_manager_role()

class BaseCreateUpdateView(LoginRequiredMixin):
  raise_exception = True

  ##
  # @brief Set request user to form params
  def get_form_kwargs(self, *args, **kwargs):
    kwargs = super().get_form_kwargs(*args, **kwargs)
    kwargs['user'] = self.request.user

    return kwargs

class CustomDeleteView(LoginRequiredMixin, IsOwner, DeleteView):
  raise_exception = True
  http_method_names = ['post']
  model = None
  success_url = None

class DjangoBreadcrumbsMixin(CrumblesViewMixin):
  ##
  # @brief URL resolver
  # @param args positional arguments
  # @param kwargs named arguments
  # @return Reconstructed link from human readable expression
  def url_resolve(self, *args, **kwargs):
    return reverse(*args, **kwargs)

  ##
  # @brief Create instance of breadcrumbs
  # @param cls class definition
  # @param url_name Target URL name
  # @param title Page title
  # @param parent_view_class Parent classname of breadcrumbs
  # @param url_keys Positional arguments of target URL
  # @return crumbles list of breadcrumb's instance
  @classmethod
  def get_target_crumbles(cls, url_name, title, parent_view_class=None, url_keys=None):
    if parent_view_class is None:
      # In the case of getting current crumbles
      crumbles = (
        CrumbleDefinition(url_name=url_name, title=title),
      )
    else:
      _kwargs = dict([(key, attrgetter(key)) for key in url_keys]) if url_keys is not None else {}
      # In the case of including parent crumbles
      crumbles = parent_view_class.crumbles + (
        CrumbleDefinition(url_name=url_name, url_resolve_kwargs=_kwargs, title=title),
      )

    return crumbles

class Index(TemplateView, DjangoBreadcrumbsMixin):
  template_name = 'index.html'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='utils:index',
    title=gettext_lazy('Home'),
  )

  ##
  # @brief Get context data
  # @param kwargs named arguments
  # @return context context which is used in template file
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['hash_value'] = get_digest()

    return context