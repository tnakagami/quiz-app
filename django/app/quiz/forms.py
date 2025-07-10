from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy
from utils.models import DualListbox
from utils.forms import (
  BaseFormWithCSS,
  ModelFormBasedOnUser,
)
from utils.widgets import CustomRadioSelect
from . import models

UserModel = get_user_model()

##
# @brief Judge whether input value is true or not.
# @return bool Judgement result
# @retval True  The value is `True` in python.
# @retval False The value is `False` in python.
def bool_converter(value):
  return value not in ['False', 'false', '0']

class GenreForm(forms.ModelForm):
  template_name = 'renderer/custom_form.html'

  class Meta:
    model = models.Genre
    fields = ('name', 'is_enabled')
    widgets = {
      'name': forms.TextInput(attrs={
        'class': 'form-control',
      }),
    }

  is_enabled = forms.TypedChoiceField(
    label=gettext_lazy('Enable/Disable'),
    coerce=bool_converter,
    initial=True,
    empty_value=True,
    choices=(
      (True, gettext_lazy('Enable')),
      (False, gettext_lazy('Disable')),
    ),
    widget=CustomRadioSelect(attrs={
      'class': 'form-check form-check-inline',
      'input-class': 'form-check-input',
      'label-class': 'form-check-label',
    }),
    help_text=gettext_lazy('Describes whether this genre is enabled or not.'),
  )

class QuizSearchForm(forms.Form):
  dual_listbox_template_name = 'renderer/custom_dual_listbox_preprocess.html'
  template_name = 'renderer/custom_form.html'
  field_order = ('genres', 'creators', 'is_and_op')

  genres = forms.MultipleChoiceField(
    label=gettext_lazy('Genre'),
    choices=[],
    required=False,
    widget=forms.SelectMultiple(attrs={
      'id': 'genreList',
      'data-available': gettext_lazy('Available genres (The number of quizzes)'),
      'data-selected': gettext_lazy('Assigned genres (The number of quizzes)'),
      'class': 'custom-multi-selectbox',
    }),
  )
  creators = forms.MultipleChoiceField(
    label=gettext_lazy('Creator'),
    choices=[],
    required=False,
    widget=forms.SelectMultiple(attrs={
      'id': 'creatorList',
      'data-available': gettext_lazy('Available creators (The number of quizzes, Code)'),
      'data-selected': gettext_lazy('Assigned creators (The number of quizzes, Code)'),
      'class': 'custom-multi-selectbox',
    }),
  )

  is_and_op = forms.TypedChoiceField(
    label=gettext_lazy('Search condition'),
    coerce=bool_converter,
    initial=False,
    empty_value=False,
    choices=(
      (True, gettext_lazy('AND')),
      (False, gettext_lazy('OR')),
    ),
    widget=CustomRadioSelect(attrs={
      'class': 'form-check form-check-inline',
      'input-class': 'form-check-input',
      'label-class': 'form-check-label',
    }),
    help_text=gettext_lazy('Describes whether the search condition is "OR" or not.'),
  )

  ##
  # @brief Constructor of QuizSearchForm
  # @param args Positional arguments
  # @param kwargs Named arguments
  def __init__(self, user, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.user = user
    # Set genre's choices
    self.fields['genres'].choices = [
      (str(instance.pk), f'{instance}({instance.quizzes.all().count()})')
      for instance in models.Genre.objects.collect_active_genres()
    ]
    # Set creator's choices
    if self.user.has_manager_role():
      self.fields['creators'].choices = [
        (str(instance.pk), f'{instance}({instance.quizzes.all().count()},{instance.code})')
        for instance in UserModel.objects.collect_creators()
      ]
    else:
      ##
      # If the request user's role is `CREATOR`, then this system hides the `creators` field.
      self.fields['creators'].choices = [(str(self.user.pk), str(self.user))]
      self.fields['creators'].widget = forms.HiddenInput()
    self.dual_listbox = DualListbox()

  ##
  # @brief Filtering queryset
  # @param queryset Input queryset
  # @return queryset Filtered queryset based on genres and creators
  def filtering(self, queryset):
    if self.is_valid():
      genres = self.cleaned_data.get('genres') or None
      creators = self.cleaned_data.get('creators') or None
      is_and_op = self.cleaned_data.get('is_and_op')
      queryset = models.Quiz.objects.collect_quizzes(
        queryset=queryset,
        creators=creators,
        genres=genres,
        is_and_op=is_and_op,
      )

    return queryset

  ##
  # @brief Get options of select element
  # @return options JSON data of option element which consists of primary-key, label-name, and selected-or-not
  @property
  def get_genre_options(self):
    all_genres = models.Genre.objects.collect_active_genres()

    if self.user.has_manager_role():
      callback = lambda item: item.quizzes.all().count()
    else:
      callback = lambda item: item.quizzes.all().filter(creator=self.user).count()
    options = self.dual_listbox.collect_options_of_items(all_genres, callback=callback)

    return options

  ##
  # @brief Get options of select element
  # @return options JSON data of option element which consists of primary-key, label-name, and selected-or-not
  @property
  def get_creator_options(self):
    callback = lambda creator: f'{creator.quizzes.all().count()},{creator.code}'

    if self.user.has_manager_role():
      # In the case of that the request user has manager role (e.g., MANAGER or superuser)
      all_creators = UserModel.objects.collect_creators()
      selected_ones = None
    else:
      # In the case of that the request user is a quiz owner
      all_creators = UserModel.objects.filter(pk__in=[self.user.pk])
      selected_ones = all_creators
    # Collect option data based on all creators and selected ones
    options = self.dual_listbox.collect_options_of_items(all_creators, selected_ones, callback=callback)

    return options

class QuizForm(ModelFormBasedOnUser):
  owner_name = 'creator'

  class Meta:
    model = models.Quiz
    fields = ('genre', 'question', 'answer', 'is_completed')
    widgets = {
      'genre': forms.Select(attrs={
        'class': 'form-select',
      }),
      'question': forms.Textarea(attrs={
        'class': 'form-control',
        'rows': '10',
        'cols': '40',
        'style': 'resize: none;',
      }),
      'answer': forms.Textarea(attrs={
        'class': 'form-control',
        'rows': '2',
        'cols': '40',
        'style': 'resize: none;',
      }),
    }

  is_completed = forms.TypedChoiceField(
    label=gettext_lazy('Created/Creating'),
    coerce=bool_converter,
    initial=False,
    empty_value=False,
    choices=(
      (True, gettext_lazy('Created')),
      (False, gettext_lazy('Creating')),
    ),
    widget=CustomRadioSelect(attrs={
      'class': 'form-check form-check-inline',
      'input-class': 'form-check-input',
      'label-class': 'form-check-label',
    }),
    help_text=gettext_lazy('Describes whether the creation of this quiz is completed or not.'),
  )

  ##
  # @brief Constructor of QuizForm
  # @param args Positional arguments
  # @param kwargs Named arguments
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['genre'].queryset = models.Genre.objects.collect_active_genres()

  ##
  # @brief Check data
  # @exception ValidationError User does not have creator role
  def clean(self):
    super().clean()

    if not self.user.has_creator_role():
      raise forms.ValidationError(
        gettext_lazy('Need to be a creator role. Please check your role.'),
        code='invalid_role',
      )

class QuizRoomSearchForm(forms.Form):
  name = forms.CharField(
    label=gettext_lazy('name'),
    max_length=128,
    required=False,
    widget=forms.TextInput(attrs={
      'class': 'form-control',
    }),
  )

  ##
  # @brief Filtering queryset
  # @param queryset Input queryset
  # @return queryset Filtered queryset based on input name
  def filtering(self, queryset):
    if self.is_valid():
      name = self.cleaned_data.get('name', '')
      queryset = queryset.filter(name__contains=name)

    return queryset

class QuizRoomForm(ModelFormBasedOnUser):
  dual_listbox_template_name = 'renderer/custom_dual_listbox_preprocess.html'
  owner_name = 'owner'
  field_order = ('name', 'genres', 'creators', 'groups', 'members', 'max_question', 'is_enabled')

  class Meta:
    model = models.QuizRoom
    fields = ('name', 'genres', 'creators', 'members', 'max_question', 'is_enabled')
    widgets = {
      'name': forms.TextInput(attrs={
        'class': 'form-control',
      }),
      'genres': forms.SelectMultiple(attrs={
        'id': 'genreList',
        'data-available': gettext_lazy('Available genres (The number of quizzes)'),
        'data-selected': gettext_lazy('Assigned genres (The number of quizzes)'),
        'class': 'custom-multi-selectbox',
      }),
      'creators': forms.SelectMultiple(attrs={
        'id': 'creatorList',
        'data-available': gettext_lazy('Available creators (The number of quizzes, Code)'),
        'data-selected': gettext_lazy('Assigned creators (The number of quizzes, Code)'),
        'class': 'custom-multi-selectbox',
      }),
      'members': forms.SelectMultiple(attrs={
        'id': 'memberList',
        'data-available': gettext_lazy('Available members'),
        'data-selected': gettext_lazy('Assigned members'),
        'class': 'custom-multi-selectbox',
      }),
      'max_question': forms.NumberInput(attrs={
        'class': 'form-control',
      }),
    }

  is_enabled = forms.TypedChoiceField(
    label=gettext_lazy('Enable/Disable'),
    coerce=bool_converter,
    initial=False,
    empty_value=False,
    choices=(
      (True, gettext_lazy('Enable')),
      (False, gettext_lazy('Disable')),
    ),
    widget=CustomRadioSelect(attrs={
      'class': 'form-check form-check-inline',
      'input-class': 'form-check-input',
      'label-class': 'form-check-label',
    }),
    help_text=gettext_lazy('Describes whether this quiz room is enabled or not.'),
  )

  groups = forms.ModelChoiceField(
    label=gettext_lazy('Individual group'),
    queryset=models.QuizRoom.objects.none(),
    required=False,
    widget=forms.Select(attrs={
      'id': 'individual-group',
      'class': 'form-control',
    }),
    help_text=gettext_lazy('Select a group to filter specific users.'),
  )

  ##
  # @brief Constructor of QuizForm
  # @param args Positional arguments
  # @param kwargs Named arguments
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['genres'].queryset = models.Genre.objects.collect_valid_genres()
    self.fields['creators'].queryset = UserModel.objects.collect_valid_creators()
    self.fields['members'].queryset = UserModel.objects.collect_valid_normal_users(self.user)
    self.fields['groups'].queryset = self.user.group_owners.all()
    self.dual_listbox = DualListbox()

  ##
  # @brief Check the relationship of relevant variables
  # @exception ValidationError Both `genres` and `creators` are not set.
  # @exception ValidationError The `max_question` is greater than the maximum number of quizzes.
  def clean(self):
    super().clean()
    genres = self.cleaned_data.get('genres', None)
    creators = self.cleaned_data.get('creators', None)
    max_question = self.cleaned_data.get('max_question', 0)
    # Check combination of both genres and creators
    if (genres is None or genres.count() == 0) and (creators is None or creators.count() == 0):
      raise forms.ValidationError(
        gettext_lazy('You have to assign at least one of genres and creators to the quiz room.'),
        code='invalid_assignment',
      )
    # Check the number of quizzes this system can collect
    all_relevant_quizzes = models.Quiz.objects.collect_quizzes(creators=creators, genres=genres)
    max_count = all_relevant_quizzes.count()
    # In the case of that there are not enough quizzes.
    if max_count < max_question:
      raise forms.ValidationError(
        gettext_lazy('The number of quizzes this system can set is %(max_count)s, but the requested value is %(max_question)s. Please check the condition.'),
        code='invalid_assignment',
        params={'max_question': str(max_question), 'max_count': str(max_count)},
      )

  ##
  # @brief Get genre's options of select element
  # @return options JSON data of option element which consists of primary-key, label-name, and selected-or-not
  @property
  def get_genre_options(self):
    all_genres = self.fields['genres'].queryset
    selected_genres = self.instance.genres.all() if self.instance else None
    callback = lambda genre: genre.quizzes.all().filter(is_completed=True).count()
    options = self.dual_listbox.collect_options_of_items(all_genres, selected_genres, callback=callback)

    return options

  ##
  # @brief Get creator's options of select element
  # @return options JSON data of option element which consists of primary-key, label-name, and selected-or-not
  @property
  def get_creator_options(self):
    all_creators = self.fields['creators'].queryset
    selected_creators = self.instance.creators.all() if self.instance else None
    callback = lambda creator: f'{creator.quizzes.all().filter(is_completed=True).count()},{creator.code}'
    options = self.dual_listbox.collect_options_of_items(all_creators, selected_creators, callback)

    return options

  ##
  # @brief Get member's options of select element
  # @return options JSON data of option element which consists of primary-key, label-name, and selected-or-not
  @property
  def get_member_options(self):
    all_members = self.fields['members'].queryset
    selected_members = self.instance.members.all() if self.instance else None
    callback = self.dual_listbox.user_cb
    options = self.dual_listbox.collect_options_of_items(all_members, selected_members, callback)

    return options

  ##
  # @brief Save m2m fields
  # @param instance Target instance
  # @param args Positional arguments
  # @param kwargs Named arguments
  def post_process(self, instance, *args, **kwargs):
    super().post_process(instance, *args, **kwargs)
    self.save_m2m()