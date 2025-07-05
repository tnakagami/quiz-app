import pytest
from utils.tags import custom_tags
from dataclasses import dataclass
from django.utils.http import urlencode

@dataclass
class _CustomGET(dict):
  def __init__(self, init=None):
    self.data = init if init else {}

  def copy(self):
    instance = _CustomGET(init=self.data)

    return instance

  def __setitem__(self, key, value):
    if not isinstance(key, str):
      raise Exception()

    self.data[key] = value

  def urlencode(self):
    return urlencode(self.data)

@dataclass
class _CustomRequest:
  GET: _CustomGET

@pytest.mark.customtag
def test_url_replace():
  instance = _CustomGET(init={'page': 'aaa'})
  request = _CustomRequest(GET=instance)
  output = custom_tags.url_replace(request, 'next', 'bbb')
  exact = urlencode({'page': 'aaa', 'next': 'bbb'})

  assert output == exact

class _DummyModel:
  def __init__(self, flag):
    self.flag = flag

  def has_update_permission(self, user):
    return self.flag

  def has_delete_permission(self, user):
    return self.flag

@pytest.mark.customtag
@pytest.mark.django_db
@pytest.mark.parametrize([
  'can_update',
  'can_delete',
], [
  (True, True),
  (True, False),
  (False, True),
  (False, False),
], ids=[
  'can-update-and-can-delete',
  'can-update-and-cannot-delete',
  'cannot-update-and-can-delete',
  'cannot-update-and-cannot-delete',
])
def test_check_can_update_and_can_delete(can_update, can_delete):
  update_instance = _DummyModel(can_update)
  delete_instance = _DummyModel(can_delete)

  assert custom_tags.can_update(update_instance, None) == can_update
  assert custom_tags.can_delete(delete_instance, None) == can_delete