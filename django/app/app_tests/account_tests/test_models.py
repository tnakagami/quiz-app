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

# ========
# = User =
# ========
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
   'expected',
], [
  (models.RoleType.MANAGER, 'Manager'),
  (models.RoleType.CREATOR, 'Creator'),
  (models.RoleType.GUEST, 'Guest'),
], ids=[
  'is-manager',
  'is-creator',
  'is-guest',
])
def test_get_role_label_method(role, expected):
  user = factories.UserFactory(role=role)
  label = user.get_role_label()

  assert label == expected

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'role',
  'has_manager_role',
  'has_creator_role',
  'has_guest_role',
  'is_creator',
  'is_guest',
  'is_player',
  'user_config',
], [
  # Superuser
  (models.RoleType.MANAGER,  True,  True, True,   False, False, False, {'is_staff': True,  'is_superuser': True}),
  (models.RoleType.CREATOR,  True,  True, True,   False, False, False, {'is_staff': True,  'is_superuser': True}),
  (models.RoleType.GUEST,    True,  True, True,   False, False, False, {'is_staff': True,  'is_superuser': True}),
  # Staff user
  (models.RoleType.MANAGER,  True,  True, True,   False, False, False, {'is_staff': True, 'is_superuser': False}),
  (models.RoleType.CREATOR, False,  True, True,    True, False,  True, {'is_staff': True, 'is_superuser': False}),
  (models.RoleType.GUEST,   False, False, True,   False,  True,  True, {'is_staff': True, 'is_superuser': False}),
  # Normal user
  (models.RoleType.MANAGER,  True,  True, True,   False, False, False, {'is_staff': False, 'is_superuser': False}),
  (models.RoleType.CREATOR, False,  True, True,    True, False,  True, {'is_staff': False, 'is_superuser': False}),
  (models.RoleType.GUEST,   False, False, True,   False,  True,  True, {'is_staff': False, 'is_superuser': False}),
], ids=[
  # Superuser
  'superuser-with-manager-role',
  'superuser-with-creator-role',
  'superuser-with-guest-role',
  # Staff user
  'staff-user-with-manager-role',
  'staff-user-with-creator-role',
  'staff-user-with-guest-role',
  # Normal user
  'normal-user-with-manager-role',
  'normal-user-with-creator-role',
  'normal-user-with-guest-role',
])
def test_check_role_of_usermodel(role, has_manager_role, has_creator_role, has_guest_role, is_creator, is_guest, is_player, user_config):
  user = factories.UserFactory(role=role, **user_config)

  assert user.has_manager_role() == has_manager_role
  assert user.has_creator_role() == has_creator_role
  assert user.has_guest_role() == has_guest_role
  assert user.is_creator() == is_creator
  assert user.is_guest() == is_guest
  assert user.is_player() == is_player

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_check_activation_method_of_usermodel():
  user = factories.UserFactory(is_active=False)
  user.activation()

  assert user.is_active

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'kwargs',
  'expected',
], [
  ({}, None),
  ({'from_email': 'hoge@example.com'}, 'hoge@example.com'),
], ids=[
  'kwargs-is-empty',
  'from_email-is-assigned',
])
def test_check_send_email_method_of_usermodel(mocker, kwargs, expected):
  sender_mock = mocker.patch('account.models.send_mail', return_value=None)
  user = factories.UserFactory()
  # Define positional arguments
  subject = 'test-subject'
  message = 'test message in pytest'
  user.email_user(subject, message, **kwargs)

  assert sender_mock.call_count == 1
  sender_mock.assert_called_with(subject, message, expected, [user.email]) 

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
  'role',
  'expected',
], [
  (models.RoleType.GUEST, models.RoleType.CREATOR),
  (models.RoleType.CREATOR, models.RoleType.CREATOR),
  (models.RoleType.MANAGER, models.RoleType.CREATOR),
], ids=[
  'is-guest',
  'is-creator',
  'is-manager',
])
def test_check_change_role(role, expected):
  user = factories.UserFactory(role=role)
  user.update_role()

  assert user.role == expected

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
def test_queryset_of_usermodel():
  _ = factories.UserFactory(is_active=True, is_staff=True, is_superuser=True)
  _ = factories.UserFactory(is_active=True, is_staff=True)
  _ = factories.UserFactory.create_batch(2, is_active=False)
  valid_users = factories.UserFactory.create_batch(3, is_active=True)
  queryset = models.User.objects.collect_valid_normal_users()
  pks = [user.pk for user in valid_users]

  assert queryset.count() == len(pks)
  assert all([queryset.filter(pk=pk).exists() for pk in pks])

# =================
# = Role Approval =
# =================
@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_check_role_approval_state():
  user, other = factories.UserFactory.create_batch(2)
  _ = factories.RoleApprovalFactory(user=user, is_completed=False)

  assert user.conducted_role_approval()
  assert not other.conducted_role_approval()

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
@pytest.mark.parametrize([
  'role',
  'requested',
  'expected',
], [
  (models.RoleType.GUEST,    True, False),
  (models.RoleType.GUEST,   False, True),
  (models.RoleType.CREATOR,  True, False),
  (models.RoleType.CREATOR, False, False),
  (models.RoleType.MANAGER,  True, False),
  (models.RoleType.MANAGER, False, False),
], ids=[
  'guest-with-request',
  'guest-without-request',
  'creator-with-request',
  'creator-without-request',
  'manager-with-request',
  'manager-without-request',
])
def test_check_has_request_permission_of_role_approval(role, requested, expected):
  user = factories.UserFactory(role=role)

  if requested:
    _ = factories.RoleApprovalFactory(user=user, is_completed=False)

  assert models.RoleApproval.has_request_permission(user) == expected

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'role',
  'email',
  'expected_email',
  'expected_status',
], [
  (models.RoleType.GUEST,   'someone@hoge.com', 'someone@hoge.com', False),
  (models.RoleType.CREATOR, 'someone@hoge.com', 'someone@hoge.com', False),
  (models.RoleType.MANAGER, 'someone@hoge.com', 'other@hoge.com',   True),
], ids=[
  'is-guest',
  'is-creator',
  'is-manager',
])
def test_check_update_record_method_of_role_approval(role, email, expected_email, expected_status):
  user = factories.UserFactory(email=email, role=role)
  other = factories.UserFactory(email='other@hoge.com')
  instance = factories.RoleApprovalFactory(user=other, is_completed=(not expected_status))
  instance.update_record(user)

  assert instance.user.email == expected_email
  assert instance.is_completed == expected_status

# ===================
# = IndividualGroup =
# ===================
@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_valid_friends_change():
  friends = list(factories.UserFactory.create_batch(5, is_active=True))
  user = factories.UserFactory(is_active=True, friends=friends)
  instance = factories.IndividualGroupFactory(owner=user, members=[friends[1], friends[2]])
  # Define new friends by removing the first friend (friends[0])
  new_friends = models.User.objects.filter(pk__in=[user.pk for user in friends[1:]])
  rest_friends = instance.extract_invalid_friends(new_friends)

  assert rest_friends.count() == 0

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_invalid_friends_change_in_individual_group():
  friends = list(factories.UserFactory.create_batch(5, is_active=True))
  user = factories.UserFactory(is_active=True, friends=friends)
  instance = factories.IndividualGroupFactory(owner=user, members=[friends[1], friends[2]])
  # Define new friends by removing the second friend (friends[1]) and the last friend (friends[-1])
  new_friends = models.User.objects.filter(pk__in=[friends[0].pk, friends[2].pk, friends[3].pk])
  rest_friends = instance.extract_invalid_friends(new_friends)

  assert rest_friends.count() == 1
  assert str(rest_friends[0].pk) == str(friends[1].pk)

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_invalid_members_of_individual_group():
  friends = list(factories.UserFactory.create_batch(3))
  _other = factories.UserFactory()
  owner = factories.UserFactory(friends=friends)
  instance = factories.IndividualGroupFactory(owner=owner, members=[_other, *friends])
  # Call target method
  input_friends = models.User.objects.filter(pk__in=[user.pk for user in friends])
  invalid = instance.exists_invalid_members(instance.members, input_friends)

  assert invalid

@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
@pytest.mark.parametrize([
  'friend_indices',
  'rest_count',
], [
  ([0, 1, 2], 0),
  ([0, 2, 3], 1),
], ids=[
  'vaild-friends',
  'invaild-friends',
])
def test_invalid_friends_of_individual_group(friend_indices, rest_count):
  friends = list(factories.UserFactory.create_batch(5, is_active=True))
  # Define the specific friends given by `friend_indices`
  user = factories.UserFactory(is_active=True, friends=[friends[idx] for idx in friend_indices])
  instance = factories.IndividualGroupFactory(owner=user, members=[friends[1], friends[2]])
  rest_friends = instance.extract_invalid_friends()

  assert rest_friends.count() == rest_count