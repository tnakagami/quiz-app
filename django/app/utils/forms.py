from django import forms

class BaseFormWithCSS(forms.Form):
  template_name = 'renderer/custom_form.html'

  ##
  # @brief Constructor of BaseFormWithCSS
  # @param args Positional arguments
  # @param kwargs Named arguments
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    for field in self.fields.values():
      _classes = field.widget.attrs.get('class', '')
      field.widget.attrs['class'] = f'{_classes} form-control'

import logging
logger = logging.getLogger(__name__)

class ModelFormBasedOnUser(forms.ModelForm):
  template_name = 'renderer/custom_form.html'
  owner_name = 'user'

  ##
  # @brief Constructor of ModelFormBasedOnUser
  # @param user Instance of access user
  # @param args Positional arguments
  # @param kwargs Named arguments
  def __init__(self, user, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.user = user

  ##
  # @brief Save instance with owner
  # @param args Positional arguments
  # @param kwargs Named arguments
  def save(self, *args, **kwargs):
    instance = super().save(commit=False)
    target = f'{self.owner_name}_id'
    owner = getattr(instance, target, None)
    for o in dir(instance):
      logger.info(o)

    logger.info(target)
    logger.info(owner)
    logger.info(hasattr(instance, target))
    # In the case of that the create view is called.
    if hasattr(instance, target) and owner is None:
      setattr(instance, self.owner_name, self.user)
    self.post_process(instance, *args, **kwargs)

    return instance

  ##
  # @brief Update instance after the request user is set
  # @param instance Target instance
  # @param args Positional arguments
  # @param kwargs Named arguments
  def post_process(self, instance, *args, **kwargs):
    instance.save()