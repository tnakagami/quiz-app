import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError, DataError
from datetime import datetime, timezone
from app_tests import factories
from account import models

wrapper_pystr = factories.faker.pystr

@pytest.fixture(autouse=True)
def mock_current_time(mocker):
  mocker.patch(
    'account.models.get_current_time',
    return_value=datetime(2021,7,3,10,17,48,microsecond=123456,tzinfo=timezone.utc),
  )

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_user():
  user = factories.UserFactory.build()

  assert isinstance(user, models.User)

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'email',
  'password',
  'screen_name',
  'str_val',
], [
  ('hoge@example.com', 'random-7Hook@o123', 'hogehoge', 'hogehoge'),
  ('{}@ok.com'.format('1'*121), wrapper_pystr(min_chars=128,max_chars=128), '1'*128, '1'*128),
  ('foo@ok.com', '', '', 'foo@ok.com'),
], ids=[
  'valid',
  'max-length',
  'include-empty-data',
])
def test_user_creation(mocker, email, password, screen_name, str_val):
  mocker.patch(
    'account.models.convert_timezone',
    return_value='20230103-123456.654321',
  )
  user = models.User.objects.create_user(email=email, password=password, screen_name=screen_name)

  assert user.email == email
  assert user.code == '20230103-123456.654321'
  assert user.screen_name == screen_name
  assert str(user) == str_val
  assert not user.is_staff
  assert not user.is_superuser
  assert not user.is_active
  assert user.role == models.RoleType.GUEST
  assert user.friends.all().count() == 0

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'role',
  'is_manager',
  'is_creator',
  'is_guest',
], [
  (models.RoleType.MANAGER,  True, False, False),
  (models.RoleType.CREATOR, False,  True, False),
  (models.RoleType.GUEST,   False, False, True),
], ids=[
  'role-is-manager',
  'role-is-creator',
  'role-is-guest',
])
def test_check_role_of_usermodel(role, is_manager, is_creator, is_guest):
  user = factories.UserFactory(role=role)

  assert user.is_manager() == is_manager
  assert user.is_creator() == is_creator
  assert user.is_guest() == is_guest

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_get_code_function():
  code = models._get_code()
  exact = '20210703-191748.123456'

  assert isinstance(code, str)
  assert code == exact

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_superuser_creation():
  superuser = models.User.objects.create_superuser(
    email='hoge@foo.com',
    is_staff=True,
    is_superuser=True,
  )
  assert superuser.is_staff
  assert superuser.is_superuser

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_add_friends():
  _friend = factories.UserFactory()
  user = factories.UserFactory(friends=[_friend])
  friends = user.friends.all()

  assert len(friends) == 1
  assert friends[0].pk == _friend.pk

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'options',
  'err_msg',
], [
  ({'is_staff': False, 'is_superuser': True}, 'Superuser must have is_staff=True.'),
  ({'is_staff': True, 'is_superuser': False}, 'Superuser must have is_superuser=True.'),
], ids=[
  'is-staff-false',
  'is-superuser-false',
])
def test_superuser_is_not_staffuser(options, err_msg):
  with pytest.raises(ValueError) as ex:
    _ = models.User.objects.create_superuser(
      email='hoge@foo.bar',
      **options,
    )
  assert err_msg in ex.value.args

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_empty_email():
  err_msg = 'The given email must be set.'

  with pytest.raises(ValueError) as ex:
    _ = models.User.objects.create_user(email='')
  assert err_msg in ex.value.args

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'options',
], [
  ({'email': '{}@ng.com'.format('1'*122)},),
  ({'code': '1'*23},),
  ({'screen_name': '1'*129},),
  ({'password': wrapper_pystr(min_chars=129,max_chars=129)},),
], ids=[
  'invalid-email',
  'invalid-code',
  'invalid-screen-name',
  'invalid-password',
])
def test_check_invalid_input(options):
  with pytest.raises(DataError):
    user = factories.UserFactory.build(**options)
    user.save()

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_invalid_same_email():
  email = 'hoge@foo.example'
  valid_user = factories.UserFactory(email=email)

  with pytest.raises(IntegrityError):
    invalid_user = factories.UserFactory.build(email=email)
    invalid_user.save()

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'completes',
  'expected',
], [
  ([], 0),
  ([False], 1),
  ([True], 0),
  ([False, False], 2),
  ([True, False], 1),
  ([True, True], 0),
], ids=[
  'is-empty',
  'is-false',
  'is-true',
  'only-false',
  'both-true-and-false',
  'only-true',
])
def test_check_role_approval_queryset(completes, expected):
  users = factories.UserFactory.create_batch(len(completes))
  # Create approval requests
  for user, is_completed in zip(users, completes):
    _ = factories.RoleApprovalFactory(user=user, is_completed=is_completed)
  totals = models.RoleApproval.objects.collect_targets().count()

  assert totals == expected

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_check_str_method_of_role_approval():
  user = factories.UserFactory()
  instance = factories.RoleApprovalFactory(user=user)

  assert str(instance) == str(user)

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_invalid_user_request_of_role_approval():
  user = factories.UserFactory()
  _ = factories.RoleApprovalFactory(user=user)
  err_msg = 'Your request has already registered.'

  with pytest.raises(ValidationError) as ex:
    instance = factories.RoleApprovalFactory.build(user=user)
    instance.save()

  assert err_msg in str(ex.value.args)

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'number_of_friends',
], (
  (0, ),
  (1, ),
  (2, ),
), ids=[
  'no-friends',
  'best-friend',
  'many-friends',
])
def test_check_save_method_of_individual_group(number_of_friends):
  friends = list(factories.UserFactory.create_batch(number_of_friends)) if number_of_friends > 0 else []
  owner = factories.UserFactory(friends=friends)
  instance = factories.IndividualGroupFactory.build(owner=owner, members=friends)

  try:
    instance.save()
  except Exception as ex:
    pytest.fail(f'Unexpected Error: {ex}')
  # Make exact data
  exact_instance_name = f'{instance.name}({owner})'

  assert str(instance) == exact_instance_name

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_invalid_members_of_individual_group(mocker):
  mocker.patch('account.models.IndividualGroup.clean', return_value=None)
  friends = list(factories.UserFactory.create_batch(3))
  _other = factories.UserFactory()
  owner = factories.UserFactory(friends=friends)
  instance = factories.IndividualGroupFactory(owner=owner, members=[_other, *friends])
  # Call target method
  invalid = instance._exists_invalid_members()

  assert invalid

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_check_save_method_exception_of_individual_group(mocker):
  owner = factories.UserFactory()
  instance = factories.IndividualGroupFactory.build(owner=owner)
  mocker.patch('account.models.IndividualGroup._exists_invalid_members', return_value=True)
  err_msg = "Invalid member list. Some members are assigned except owner's friends."

  with pytest.raises(ValidationError) as ex:
    instance.save()

  assert err_msg in str(ex.value.args)