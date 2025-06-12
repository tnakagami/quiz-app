import pytest
from django.utils import timezone as djangoTZ
from datetime import datetime, timezone
from utils import models

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