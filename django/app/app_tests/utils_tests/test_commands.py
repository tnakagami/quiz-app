import pytest
import argparse
from django.core.management import CommandError
from django.contrib.auth import get_user_model
from utils.management.commands import custom_createsuperuser

UserModel = get_user_model()

@pytest.fixture
def init_record(django_db_blocker):
  password = 'abc123'
  options = {
    'email': 'hoge@example.com',
    'password': password,
  }

  with django_db_blocker.unblock():
    user = UserModel.objects.create_user(**options)

  return password, user

# ==========================
# = custom_createsuperuser =
# ==========================
@pytest.mark.utils
def test_add_arguments():
  email = 'hoge@example.com'
  password = 'foobar'
  inputs = ['--email', email, '--password', password]
  command = custom_createsuperuser.Command()
  parser = argparse.ArgumentParser()
  command.add_arguments(parser)
  args = parser.parse_args(inputs)

  assert args.email == email
  assert args.password == password

@pytest.mark.utils
@pytest.mark.django_db
@pytest.mark.parametrize([
  'user_exists',
], [
  (True, ),
  (False, ),
], ids=[
  'same-superuser-exists',
  'register-superuser-for-the-first-time',
])
def test_valid_superuser(user_exists):
  options = {
    'email': 'hoge@example.com',
    'password': 'sample'
  }

  if user_exists:
    screen_name = 'admin-user'
    _ = UserModel.objects.create_superuser(**options, screen_name=screen_name)
  else:
    screen_name = 'admin'
  command = custom_createsuperuser.Command()
  command.handle(**options)
  user = UserModel.objects.get(email=options['email'])

  assert user.email == options['email']
  assert user.check_password(options['password'])
  assert user.screen_name == screen_name

@pytest.mark.utils
@pytest.mark.parametrize([
  'email_exists',
  'password_exists',
], [
  (False, False),
  (False, True),
  (True,  False),
], ids=[
  'all-items-are-empty',
  'only-password',
  'only-email',
])
def test_invalid_args(email_exists, password_exists):
  pairs = {
    'email':    (email_exists, 'hoge@example.com'),
    'password': (password_exists, 'abc123'),
  }
  options = {key: val for key, (flag, val) in pairs.items() if flag}
  err = '--email and --password are required options'
  command = custom_createsuperuser.Command()

  with pytest.raises(CommandError) as ex:
    command.handle(**options)

  assert err == str(ex.value)