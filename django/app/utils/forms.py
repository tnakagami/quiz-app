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
    # Replace the named argument
    kwargs['commit'] = False
    instance = super().save(*args, **kwargs)
    setattr(instance, self.owner_name, self.user)
    instance.save()

    return instance