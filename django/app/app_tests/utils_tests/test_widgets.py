import pytest
from utils import widgets

@pytest.mark.utils
@pytest.mark.widget
@pytest.mark.parametrize([
  'attrs',
  'expected_input',
  'expected_label',
], [
  ({'input-class': 'hoge', 'label-class': 'foo'}, 'hoge', 'foo'),
  (None, '', ''),
], ids=[
  'set-attributes',
  'not-set-attributes',
])
def test_check_instance_of_radio_select(attrs, expected_input, expected_label):
  widget = widgets.CustomRadioSelect(attrs)

  assert widget.input_class == expected_input
  assert widget.label_class  == expected_label

@pytest.mark.utils
@pytest.mark.widget
@pytest.mark.parametrize([
  'attrs',
  'expected_input',
  'expected_label',
], [
  ({'input-class': 'hoge', 'label-class': 'foo'}, 'hoge', 'foo'),
  (None, '', ''),
], ids=[
  'set-attributes',
  'not-set-attributes',
])
def test_check_creat_option_method_of_radio_select(attrs, expected_input, expected_label):
  widget = widgets.CustomRadioSelect(attrs)
  options = widget.create_option(
    name='bar',
    value=0,
    label='sub-label',
    selected=False,
    index=1,
  )
  keys = options.keys()

  assert 'input_class' in keys
  assert 'label_class' in keys
  assert options['input_class'] == expected_input
  assert options['label_class'] == expected_label