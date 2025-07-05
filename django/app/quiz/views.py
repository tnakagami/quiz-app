from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils.translation import gettext_lazy
from django.urls import reverse, reverse_lazy
from django.views.generic import (
  ListView,
  CreateView,
  UpdateView,
  DetailView,
)
from utils.views import (
  CanUpdate,
  IsCreator,
  IsPlayer,
  HasManagerRole,
  HasCreatorRole,
  BaseCreateUpdateView,
  CustomDeleteView,
  Index,
  DjangoBreadcrumbsMixin,
)
from . import models, forms

# =========
# = Genre =
# =========
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

# ========
# = Quiz =
# ========
class QuizListPage(LoginRequiredMixin, HasCreatorRole, ListView, DjangoBreadcrumbsMixin):
  model = models.Quiz
  template_name = 'quiz/quiz_list.html'
  paginate_by = 15
  context_object_name = 'quizzes'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:quiz_list',
    title=gettext_lazy('Quizzes'),
    parent_view_class=Index,
  )

  def get_queryset(self):
    user = self.request.user

    # In the case of that user is manager or superuser
    if user.has_manager_role():
      queryset = self.model.objects.all()
    # In the case of that user is creator
    else:
      queryset = user.quizzes.all()

    return queryset

class CreateQuizPage(BaseCreateUpdateView, IsCreator, CreateView, DjangoBreadcrumbsMixin):
  model = models.Quiz
  form_class = forms.QuizForm
  template_name = 'quiz/quiz_form.html'
  success_url = reverse_lazy('quiz:quiz_list')
  crumbles_context_attribute = 'owner'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:create_quiz',
    title=gettext_lazy('Create/Update quiz'),
    parent_view_class=QuizListPage,
  )

  ##
  # @brief Get context data
  # @param kwargs named arguments
  # @return context context which is used in template file
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    self.owner = self.request.user

    return context

class UpdateQuizPage(BaseCreateUpdateView, CanUpdate, UpdateView, DjangoBreadcrumbsMixin):
  model = models.Quiz
  form_class = forms.QuizForm
  template_name = 'quiz/quiz_form.html'
  success_url = reverse_lazy('quiz:quiz_list')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:update_quiz',
    title=gettext_lazy('Create/Update quiz'),
    parent_view_class=QuizListPage,
    url_keys=['pk'],
  )

class DeleteQuiz(CustomDeleteView):
  model = models.Quiz
  success_url = reverse_lazy('quiz:quiz_list')

# ============
# = QuizRoom =
# ============
class QuizRoomListPage(LoginRequiredMixin, ListView, DjangoBreadcrumbsMixin):
  model = models.QuizRoom
  template_name = 'quiz/room_list.html'
  paginate_by = 15
  context_object_name = 'rooms'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:room_list',
    title=gettext_lazy('Quiz rooms'),
    parent_view_class=Index,
  )

  def get_queryset(self):
    user = self.request.user

    # In the case of that user is manager or superuser
    if user.has_manager_role():
      queryset = self.model.objects.all()
    # In the case of that user is creator or guest
    else:
      queryset = self.model.objects.collect_relevant_rooms(user)

    return queryset

class CreateQuizRoomPage(BaseCreateUpdateView, IsPlayer, CreateView, DjangoBreadcrumbsMixin):
  model = models.QuizRoom
  form_class = forms.QuizRoomForm
  template_name = 'quiz/room_form.html'
  success_url = reverse_lazy('quiz:room_list')
  crumbles_context_attribute = 'owner'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:create_room',
    title=gettext_lazy('Create/Update quiz room'),
    parent_view_class=QuizRoomListPage,
  )

  ##
  # @brief Get context data
  # @param kwargs named arguments
  # @return context context which is used in template file
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    self.owner = self.request.user

    return context

class UpdateQuizRoomPage(BaseCreateUpdateView, CanUpdate, UpdateView, DjangoBreadcrumbsMixin):
  model = models.QuizRoom
  form_class = forms.QuizRoomForm
  template_name = 'quiz/room_form.html'
  success_url = reverse_lazy('quiz:room_list')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:update_room',
    title=gettext_lazy('Create/Update quiz room'),
    parent_view_class=QuizRoomListPage,
    url_keys=['pk'],
  )

class DeleteQuizRoom(CustomDeleteView):
  model = models.QuizRoom
  success_url = reverse_lazy('quiz:room_list')

class EnterQuizRoom(LoginRequiredMixin, UserPassesTestMixin, DetailView, DjangoBreadcrumbsMixin):
  raise_exception = True
  model = models.QuizRoom
  template_name = 'quiz/playing_room.html'
  context_object_name = 'room'

  ##
  # @brief Check whether request user can access to target page or not
  # @return bool Judgement result
  # @retval True Request user can access to the page
  # @retval False Request user can access to the page except superuser
  def test_func(self):
    instance = self.get_object()
    is_valid = instance.is_assigned(self.request.user)

    return is_valid

  ##
  # @brief Get context data
  # @param kwargs named arguments
  # @return context context which is used in template file
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    instance = context[self.context_object_name]
    # Set breadcrumbs
    self.crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
      url_name='quiz:enter_room',
      title=instance.name,
      parent_view_class=QuizRoomListPage,
      url_keys=['pk'],
    )

    return context