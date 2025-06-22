from django import forms

class CustomSwitchInput(forms.CheckboxInput):
  template_name = 'widgets/custom_switch.html'