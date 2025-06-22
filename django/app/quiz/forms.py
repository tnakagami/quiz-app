from django import forms
from django.utils.translation import gettext_lazy
from utils.forms import BaseFormWithCSS, ModelFormBasedOnUser
from utils.widgets import CustomRadioSelect
from . import models

import logging
logger = logging.getLogger(__name__)

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

  def clean_is_enabled(self):
    is_enabled = self.cleaned_data.get('is_enabled')
    logger.info(is_enabled)

    return is_enabled

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
      }),
      'answer': forms.Textarea(attrs={
        'class': 'form-control',
      }),
    }

  is_completed = forms.TypedChoiceField(
    label=gettext_lazy('Created/Creating'),
    coerce=bool_converter,
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

class QuizRoom(ModelFormBasedOnUser):
  owner_name = 'owner'

  class Meta:
    model = models.QuizRoom
    fields = ('name', 'genres', 'creators', 'members', 'max_question', 'is_enabled')
    widgets = {
      'name': forms.TextInput(attrs={
        'class': 'form-control',
      }),
      'genres': forms.SelectMultiple(attrs={
        'class': 'custom-multi-selectbox',
      }),
      'creators': forms.SelectMultiple(attrs={
        'class': 'custom-multi-selectbox',
      }),
      'members': forms.SelectMultiple(attrs={
        'class': 'custom-multi-selectbox',
      }),
      'max_question': forms.NumberInput(attrs={
        'class': 'form-control',
      }),
    }

  is_enabled = forms.TypedChoiceField(
    label=gettext_lazy('Enable/Disable'),
    coerce=bool_converter,
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

  ##
  # @brief Constructor of QuizForm
  # @param args Positional arguments
  # @param kwargs Named arguments
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['genres'].queryset = models.Genre.objects.collect_active_genres()
    self.fields['creators'].queryset = UserModel.objects.collect_creators()
    self.fields['members'].queryset = UserModel.objects.collect_valid_normal_users()