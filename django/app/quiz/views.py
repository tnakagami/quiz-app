from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy
from django.urls import reverse, reverse_lazy
from django.views.generic import (
  ListView,
  CreateView,
  UpdateView,
)
from utils.views import (
  IsCreator,
  HasManagerRole,
  HasCreatorRole,
  BaseCreateUpdateView,
  CustomDeleteView,
  Index,
  DjangoBreadcrumbsMixin,
)
from . import models, forms

class GenreListPage(LoginRequiredMixin, HasManagerRole, ListView, DjangoBreadcrumbsMixin):
  model = models.Genre
  template_name = 'quiz/genre_list.html'
  paginate_by = 15
  queryset = models.Genre.objects.all()
  context_object_name = 'genres'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:genre_list',
    title=gettext_lazy('Genres'),
    parent_view_class=Index,
  )

class CreateGenrePage(LoginRequiredMixin, HasManagerRole, CreateView, DjangoBreadcrumbsMixin):
  model = models.Genre
  form_class = forms.GenreForm
  template_name = 'quiz/genre_form.html'
  success_url = reverse_lazy('quiz:genre_list')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:create_genre',
    title=gettext_lazy('Create/Update genre'),
    parent_view_class=GenreListPage,
  )

class UpdateGenrePage(LoginRequiredMixin, HasManagerRole, UpdateView, DjangoBreadcrumbsMixin):
  model = models.Genre
  form_class = forms.GenreForm
  template_name = 'quiz/genre_form.html'
  success_url = reverse_lazy('quiz:genre_list')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:update_genre',
    title=gettext_lazy('Create/Update genre'),
    parent_view_class=GenreListPage,
    url_keys=['pk'],
  )