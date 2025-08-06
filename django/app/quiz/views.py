from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import StreamingHttpResponse, JsonResponse
from django.utils.translation import gettext_lazy
from django.urls import reverse, reverse_lazy
from django.views.generic import (
  View,
  ListView,
  CreateView,
  UpdateView,
  DetailView,
  FormView,
)
from utils.models import streaming_csv_file
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
  paginate_by = 50
  queryset = models.Genre.objects.all()
  context_object_name = 'genres'
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:genre_list',
    title=gettext_lazy('Genre list'),
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
  form_class = forms.QuizSearchForm
  context_object_name = 'quizzes'
  http_method_names = ['get', 'post']
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:quiz_list',
    title=gettext_lazy('Quiz list'),
    parent_view_class=Index,
  )

  ##
  # @brief Get queryset
  # @return queryset Fitered queryset
  def get_queryset(self):
    return self.model.objects.user_relevant_quizzes(self.request.user)

  ##
  # @brief Process POST request
  # @param request Instance of HttpRequest
  # @param args Positional arguments
  # @param kwargs named arguments
  # @return Instance of HttpResponse
  def post(self, request, *args, **kwargs):
    params = self.request.POST.copy() or {}
    self.form = self.form_class(user=self.request.user, data=params)
    # Update object list in POST request
    self.object_list = self.form.filtering(self.get_queryset())
    context = self.get_context_data(form=self.form)

    return self.render_to_response(context)

  ##
  # @brief Get context data
  # @param kwargs named arguments
  # @return context context which is used in template file
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    # In the case of calling GET method
    if 'form' not in context.keys():
      context['form'] = self.form_class(user=self.request.user)

    return context

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
  form_class = forms.QuizRoomSearchForm
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:room_list',
    title=gettext_lazy('Quiz room list'),
    parent_view_class=Index,
  )

  ##
  # @brief Get queryset
  # @return queryset Fitered queryset
  def get_queryset(self):
    rooms = self.model.objects.collect_relevant_rooms(self.request.user)
    # Filtering queryset
    params = self.request.GET.copy() or {}
    self.form = self.form_class(data=params)
    queryset = self.form.filtering(rooms)

    return queryset

  ##
  # @brief Get context data
  # @param kwargs named arguments
  # @return context context which is used in template file
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['form'] = self.form

    return context

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

# ===================
# = Download/Upload =
# ===================
class UploadGenrePage(LoginRequiredMixin, HasManagerRole, FormView, DjangoBreadcrumbsMixin):
  raise_exception = True
  form_class = forms.GenreUploadForm
  template_name = 'quiz/upload_genre.html'
  success_url = reverse_lazy('quiz:genre_list')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:upload_genre',
    title=gettext_lazy('Upload genre'),
    parent_view_class=GenreListPage,
  )

  ##
  # @brief Post process for form validation
  # @param form Instance of `self.form_class`
  # @return response Instance of HttpResponse
  def form_valid(self, form):
    from django.core.exceptions import NON_FIELD_ERRORS
    # Store genres based on uploaded file
    form.register_genres()
    # Check errors
    if not form.has_error(NON_FIELD_ERRORS):
      response = super().form_valid(form)
    else:
      response = super().form_invalid(form)

    return response

class DownloadGenrePage(LoginRequiredMixin, HasCreatorRole, FormView, DjangoBreadcrumbsMixin):
  raise_exception = True
  form_class = forms.GenreDownloadForm
  template_name = 'quiz/download_genre.html'
  success_url = reverse_lazy('quiz:quiz_list')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:download_genre',
    title=gettext_lazy('Download genres'),
    parent_view_class=QuizListPage,
  )

  ##
  # @brief Post process for form validation
  # @param form Instance of `self.form_class`
  # @return response Instance of StreamingHttpResponse
  def form_valid(self, form):
    kwargs = form.create_response_kwargs()
    filename = kwargs['filename']
    # Create response
    response = StreamingHttpResponse(
      streaming_csv_file(kwargs['rows'], header=kwargs['header']),
      content_type='text/csv;charset=UTF-8',
      headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
    response.set_cookie(
      'genre_download_status',
      value='completed',
      max_age=settings.CSV_DOWNLOAD_MAX_AGE,
      secure=True,
    )

    return response

class UploadQuizPage(LoginRequiredMixin, HasCreatorRole, FormView, DjangoBreadcrumbsMixin):
  raise_exception = True
  form_class = forms.QuizUploadForm
  template_name = 'quiz/upload_quiz.html'
  success_url = reverse_lazy('quiz:quiz_list')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:upload_quiz',
    title=gettext_lazy('Upload quiz'),
    parent_view_class=QuizListPage,
  )

  ##
  # @brief Set request user to form params
  # @param args Positional arguments
  # @param kwargs named arguments
  # @return kwargs named arguments to create form instance
  def get_form_kwargs(self, *args, **kwargs):
    kwargs = super().get_form_kwargs(*args, **kwargs)
    kwargs['user'] = self.request.user

    return kwargs

  ##
  # @brief Post process for form validation
  # @param form Instance of `self.form_class`
  # @return response Instance of HttpResponse
  def form_valid(self, form):
    from django.core.exceptions import NON_FIELD_ERRORS
    # Store quizzes based on uploaded file
    form.register_quizzes()
    # Check errors
    if not form.has_error(NON_FIELD_ERRORS):
      response = super().form_valid(form)
    else:
      response = super().form_invalid(form)

    return response

class DownloadQuizPage(LoginRequiredMixin, HasCreatorRole, FormView, DjangoBreadcrumbsMixin):
  raise_exception = True
  form_class = forms.QuizDownloadForm
  template_name = 'quiz/download_quiz.html'
  success_url = reverse_lazy('quiz:quiz_list')
  crumbles = DjangoBreadcrumbsMixin.get_target_crumbles(
    url_name='quiz:download_quiz',
    title=gettext_lazy('Download quiz'),
    parent_view_class=QuizListPage,
  )

  ##
  # @brief Set request user to form params
  # @param args Positional arguments
  # @param kwargs named arguments
  # @return kwargs named arguments to create form instance
  def get_form_kwargs(self, *args, **kwargs):
    kwargs = super().get_form_kwargs(*args, **kwargs)
    kwargs['user'] = self.request.user

    return kwargs

  ##
  # @brief Post process for form validation
  # @param form Instance of `self.form_class`
  # @return response Instance of StreamingHttpResponse
  def form_valid(self, form):
    kwargs = form.create_response_kwargs()
    filename = kwargs['filename']
    # Create response
    response = StreamingHttpResponse(
      streaming_csv_file(kwargs['rows'], header=kwargs['header']),
      content_type='text/csv;charset=UTF-8',
      headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
    response.set_cookie(
      'quiz_download_status',
      value='completed',
      max_age=settings.CSV_DOWNLOAD_MAX_AGE,
      secure=True,
    )

    return response

class QuizAjaxResponse(LoginRequiredMixin, HasCreatorRole, View):
  raise_exception = True
  http_method_names = ['get']

  ##
  # @brief Process GET method requested by ajax function
  # @param request Instance of HttpRequest
  # @param args Positional arguments
  # @param kwargs named arguments
  # @return response Instance of JsonResponse
  def get(self, request, *args, **kwargs):
    quizzes = models.Quiz.get_quizzes(request.user)
    response = JsonResponse({'quizzes': quizzes}, json_dumps_params={'ensure_ascii': False})

    return response