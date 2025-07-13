import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone as djangoTZ
from dataclasses import dataclass
from datetime import datetime, timezone
from app_tests import factories, g_compare_options
from utils import models
import json

UserModel = get_user_model()
g_current_time = datetime(2021,7,3,10,17,48,microsecond=123456,tzinfo=timezone.utc)

@pytest.fixture(autouse=True)
def mock_current_time(mocker):
  mocker.patch('utils.models.timezone.now', return_value=g_current_time)

@pytest.mark.utils
@pytest.mark.model
def test_check_get_current_time_function():
  estimated_time = models.get_current_time()

  assert g_current_time == estimated_time

@pytest.mark.utils
@pytest.mark.model
@pytest.mark.parametrize([
  'options',
  'exact_time',
], [
  ({'is_string': False}, djangoTZ.localtime(g_current_time)),
  ({'is_string': True, 'strformat': 'Ymd'}, '20210703'),
  ({'is_string': True, 'strformat': 'Ymd-His.u'}, '20210703-191748.123456'),
  ({'is_string': True}, '2021-07-03'),
])
def test_check_convert_timezone(options, exact_time):
  estimated_time = models.convert_timezone(g_current_time, **options)

  assert estimated_time == exact_time

@pytest.mark.utils
@pytest.mark.model
def test_check_get_digest_method(settings, mocker):
  class FakeObj:
    def hexdigest(self):
      return 'dummy'

  mocker.patch('utils.models.convert_timezone', return_value='2023-07-09(1)')
  sha256_mock = mocker.patch('utils.models.hashlib.sha256', return_value=FakeObj())
  # Call target function
  ret = models.get_digest()
  # Create expected value
  args, _ = sha256_mock.call_args
  expected_input_val = f'2023-07-09(1)#{settings.HASH_SALT}'.encode()

  assert args[0] == expected_input_val
  assert ret == 'dummy'

@dataclass
class DummyModel:
  pk: str
  data: str
  name: str = 'hoge'
  code: int = 123

  def __str__(self):
    return self.data

@pytest.mark.utils
@pytest.mark.model
@pytest.mark.parametrize([
  'items',
  'kwargs',
  'expected',
], [
  ([], {}, []),
  ([DummyModel(pk='a3', data='v1')], {}, [('v1', 'a3', True)]),
  ([DummyModel(pk='a3', data='v1'),DummyModel(pk='a4', data='v2')], {}, [('v1', 'a3', True), ('v2', 'a4', True)]),
  ([DummyModel(pk='a3', data='v1'),DummyModel(pk='a4', data='v2')], {'is_selected': False}, [('v1', 'a3', False), ('v2', 'a4', False)]),
  ([DummyModel(pk='b3', data='v3', code=143)], {'callback': lambda instance: instance.code}, [('v3(143)', 'b3', True)]),
], ids=[
  'empty-list',
  'only-one-item',
  'many-items',
  'is-selected-true',
  'set-callback',
])
def test_creat_options_of_dual_listbox(items, kwargs, expected):
  instance = models.DualListbox()
  options = instance.create_options(items, **kwargs)

  assert all([all([x_val == y_val for x_val, y_val in zip(xs, ys)]) for xs, ys in zip(options, expected)])

@pytest.mark.utils
@pytest.mark.model
def test_check_convertor_of_dual_listbox():
  data = ('hoge-2', 'c1', False)
  instance = models.DualListbox()
  out = instance.convertor(data)

  assert 'text' in out
  assert out['text'] == 'hoge-2'
  assert 'value' in out
  assert out['value'] == 'c1'
  assert 'selected' in out
  assert not out['selected']

@pytest.mark.utils
@pytest.mark.model
@pytest.mark.parametrize([
  'data_type',
], [
  ('empty', ),
  ('single', ),
  ('multi', ),
], ids=lambda xs: str(xs))
def test_check_convert2json_of_dual_listbox(data_type):
  patterns = {
    'empty': [],
    'single': [('hoge-2', 'c1', False)],
    'multi': [('hoge-2', 'c1', False), ('foo-3', 'd1', True)],
  }
  exacts = {
    'empty': json.dumps([]),
    'single': json.dumps([{"text": 'hoge-2', "value": 'c1', "selected": False}]),
    'multi': json.dumps([{"text": 'hoge-2', "value": 'c1', "selected": False}, {"text": 'foo-3', "value": 'd1', "selected": True}]),
  }
  data = patterns[data_type]
  expected = exacts[data_type]
  instance = models.DualListbox()
  out = instance.convert2json(data)

  assert isinstance(out, str)
  assert out == expected

@pytest.mark.utils
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'selected_type',
  'exact_type',
  'exists_callback',
], [
  ('none', 'all', False),
  ('none', 'all', True),
  ('single', 'single', False),
  ('single', 'single', True),
  ('multi', 'multi', False),
  ('multi', 'multi', True),
], ids=[
  'no-data-without-callback',
  'no-data-with-callback',
  'single-data-without-callback',
  'single-data-with-callback',
  'multi-data-without-callback',
  'multi-data-with-callback',
])
def test_collect_options_of_items(selected_type, exact_type, exists_callback):
  users = factories.UserFactory.create_batch(3, is_active=True)
  instance = models.DualListbox()
  callback = instance.user_cb if exists_callback else None
  exacts_cb = (lambda val: f'({callback(val)})') if exists_callback else (lambda val: '')
  patterns = {
    'none':   {'callback': callback},
    'single': {'selected_items': UserModel.objects.filter(pk__in=[users[0].pk]), 'callback': callback},
    'multi':  {'selected_items': UserModel.objects.filter(pk__in=[users[0].pk, users[-1].pk]), 'callback': callback},
  }
  exacts = {}
  exacts['all'] = [
    {"text": f'{user}{exacts_cb(user)}', "value": str(user.pk), 'selected': False} for user in users
  ]
  exacts['single'] = [
    {"text": f'{users[0]}{exacts_cb(users[0])}', "value": str(users[0].pk), 'selected': True},
    {"text": f'{users[1]}{exacts_cb(users[1])}', "value": str(users[1].pk), 'selected': False},
    {"text": f'{users[2]}{exacts_cb(users[2])}', "value": str(users[2].pk), 'selected': False},
  ]
  exacts['multi'] = [
    {"text": f'{users[0]}{exacts_cb(users[0])}', "value": str(users[0].pk), 'selected': True},
    {"text": f'{users[2]}{exacts_cb(users[2])}', "value": str(users[2].pk), 'selected': True},
    {"text": f'{users[1]}{exacts_cb(users[1])}', "value": str(users[1].pk), 'selected': False},
  ]
  # Get options
  kwargs = patterns[selected_type]
  all_items = UserModel.objects.filter(pk__in=list(map(lambda val: val.pk, users))).all()
  str_options = instance.collect_options_of_items(all_items, **kwargs)
  options = json.loads(str_options)
  expected = exacts[exact_type]

  assert isinstance(str_options, str)
  assert g_compare_options(options, expected)

@pytest.mark.utils
@pytest.mark.model
@pytest.mark.parametrize([
  'value',
  'expected',
], [
  ('True', True),
  ('true', True),
  ('1', True),
  ('False', False),
  ('false', False),
  ('0', False),
], ids=[
  'python-style-true',
  'javascript-style-true',
  'number-style-true',
  'python-style-false',
  'javascript-style-false',
  'number-style-false',
])
def test_bool_converter(value, expected):
  estimated = models.bool_converter(value)

  assert estimated == expected

@pytest.mark.utils
@pytest.mark.model
def test_echo_buffer():
  buffer = models._EchoBuffer()
  val = buffer.write(5)

  assert val == 5

@pytest.mark.utils
@pytest.mark.model
def test_streaming_csv_file():
  compare_array = lambda xs, ys: all(_x == _y for _x, _y in zip(xs, ys))
  to_joined_str = lambda xs: ','.join([str(val) for val in xs])
  remove_return_code = lambda val: val.strip()
  # Define data
  rows = [
    [1, 2],
    [3, 4],
    [7, 9],
  ]
  records = (row for row in rows)
  header = ['col1', 'col2']
  item_gen = models.streaming_csv_file(records, header)
  out_bom = next(item_gen)
  out_header = next(item_gen)
  _row0 = next(item_gen)
  _row1 = next(item_gen)
  _row2 = next(item_gen)

  with pytest.raises(StopIteration):
    _ = next(item_gen)

  assert b'\xEF\xBB\xBF' == remove_return_code(out_bom)
  assert to_joined_str(header)  == remove_return_code(out_header)
  assert to_joined_str(rows[0]) == remove_return_code(_row0)
  assert to_joined_str(rows[1]) == remove_return_code(_row1)
  assert to_joined_str(rows[2]) == remove_return_code(_row2)