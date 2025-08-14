import pytest
from app_tests import factories
from passkey import models, forms

@pytest.mark.passkey
@pytest.mark.form
@pytest.mark.django_db
class TestUserPasskeyForm:
  @pytest.mark.parametrize([
    'is_enabled',
    'expected',
  ], [
    (True, False),
    (False, True),
  ], ids=[
    'from-enable-to-disable',
    'from-disable-to-enable',
  ])
  def test_update_enable_state(self, get_test_user, is_enabled, expected):
    _, user = get_test_user
    form = forms.UserPasskeyForm(data={})
    form.instance = factories.UserPasskeyFactory(user=user, is_enabled=is_enabled)
    is_valid = form.is_valid()
    target = form.save()
    instance = models.UserPasskey.objects.get(pk=target.pk)

    assert is_valid
    assert instance.is_enabled == expected

  def test_no_commit(self, get_test_user):
    _, user = get_test_user
    original = factories.UserPasskeyFactory(user=user, is_enabled=True)
    form = forms.UserPasskeyForm(data={})
    form.instance = original
    is_valid = form.is_valid()
    target = form.save(commit=False)
    instance = models.UserPasskey.objects.get(pk=target.pk)

    assert is_valid
    assert instance.is_enabled != original.is_enabled