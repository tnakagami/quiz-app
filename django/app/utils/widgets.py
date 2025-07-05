from django import forms

class CustomSwitchInput(forms.CheckboxInput):
  template_name = 'widgets/custom_switch.html'

class CustomRadioSelect(forms.RadioSelect):
  input_class = ''
  label_class = ''
  template_name = 'widgets/custom_radio.html'
  option_template_name = 'widgets/custom_radio_option.html'

  ##
  # @brief Constructor of CustomRadioSelect
  def __init__(self, attrs=None):
    if attrs is not None:
      self.input_class = attrs.pop('input-class', self.input_class)
      self.label_class = attrs.pop('label-class', self.label_class)
    super().__init__(attrs)

  ##
  # @brief Get options used in `self.option_template_name`
  # @param args Positional arguments
  # @param kwargs Named arguments
  # @return options Options of radio button
  def create_option(self, *args, **kwargs):
    options = super().create_option(*args, **kwargs)
    options['input_class'] = self.input_class
    options['label_class'] = self.label_class

    return options