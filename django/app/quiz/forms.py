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
        'data-available': gettext_lazy('Available genres'),
        'data-selected': gettext_lazy('Assigned genres'),
        'class': 'custom-multi-selectbox',
      }),
      'creators': forms.SelectMultiple(attrs={
        'id': 'creatorList',
        'data-available': gettext_lazy('Available creators'),
        'data-selected': gettext_lazy('Assigned creators'),
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
    self.fields['genres'].queryset = models.Genre.objects.collect_active_genres()
    self.fields['creators'].queryset = UserModel.objects.collect_creators()
    self.fields['members'].queryset = UserModel.objects.collect_valid_normal_users()
    self.fields['groups'].queryset = self.user.group_owners.all()
    self.dual_listbox = DualListbox()

  ##
  # @brief Check whether all members are creators or not
  # @exception ValidationError Some users's role is not CREATOR
  def clean_creators(self):
    creators = self.cleaned_data.get('creators')

    if not self._meta.model.is_only_creator(creators):
      raise forms.ValidationError(
        gettext_lazy('You have to assign only creators.'),
        code='invalid_users',
      )

    return creators

  ##
  # @brief Check whether all members are players or not
  # @exception ValidationError Some members are not players
  def clean_members(self):
    members = self.cleaned_data.get('members')

    if not self._meta.model.is_only_player(members):
      raise forms.ValidationError(
        gettext_lazy('You have to assign only players whose role is `Guest` or `Creator`.'),
        code='invalid_users',
      )

    return members

  ##
  # @brief Get genre's options of select element
  # @return options JSON data of option element which consists of primary-key, label-name, and selected-or-not
  @property
  def get_genre_options(self):
    all_genres = self.fields['genres'].queryset
    selected_genres = self.instance.genres.all() if self.instance else None
    options = self.dual_listbox.collect_options_of_items(all_genres, selected_genres)

    return options

  ##
  # @brief Get creator's options of select element
  # @return options JSON data of option element which consists of primary-key, label-name, and selected-or-not
  @property
  def get_creator_options(self):
    all_creators = self.fields['creators'].queryset
    selected_creators = self.instance.creators.all() if self.instance else None
    callback = self.dual_listbox.user_cb
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