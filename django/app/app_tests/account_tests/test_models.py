import pytest
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.db.utils import IntegrityError, DataError
from datetime import datetime, timezone
from app_tests import (
  factories,
  g_generate_item,
  g_compare_options,
)
from account import models

f_pystr = factories.faker.pystr

@pytest.fixture(autouse=True)
def mock_current_time(mocker):
  mocker.patch(
    'account.models.get_current_time',
    return_value=datetime(2021,7,3,10,17,48,microsecond=123456,tzinfo=timezone.utc),
  )

# ====================
# = Global functions =
# ====================
@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
def test_get_code_function():
  code = models._get_code()
  exact = '20210703-191748.123456'

  assert isinstance(code, str)
  assert code == exact

# ========
# = User =
# ========
@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
class TestUser:
  def test_user_instance_type(self):
    user = factories.UserFactory.build()

    assert isinstance(user, models.User)

  def test_add_friends(self):
    _friend = factories.UserFactory()
    user = factories.UserFactory(friends=[_friend])
    friends = user.friends.all()

    assert friends.count() == 1
    assert friends[0].pk == _friend.pk

  @pytest.mark.parametrize([
    'email',
    'password',
    'screen_name',
    'str_val',
  ], [
    ('hoge@example.com', 'random-7Hook@o123', 'hogehoge', 'hogehoge'),
    ('{}@ok.com'.format('1'*121), f_pystr(min_chars=128,max_chars=128), '1'*128, '1'*128),
    ('foo@ok.com', '', '', 'foo@ok.com'),
  ], ids=[
    'valid',
    'max-length',
    'include-empty-data',
  ])
  def test_user_creation(self, mocker, email, password, screen_name, str_val):
    mocker.patch('account.models.convert_timezone', return_value='20230103-123456.654321')
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

  def test_superuser_creation(self):
    superuser = models.User.objects.create_superuser(
      email='hoge@foo.com',
      is_staff=True,
      is_superuser=True,
    )
    assert superuser.is_staff
    assert superuser.is_superuser

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
  def test_get_role_label(self, role, expected):
    user = factories.UserFactory(role=role)
    label = user.get_role_label()

    assert label == expected

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
  def test_check_role(self, role, has_manager_role, has_creator_role, has_guest_role, is_creator, is_guest, is_player, user_config):
    user = factories.UserFactory(role=role, **user_config)

    assert user.has_manager_role() == has_manager_role
    assert user.has_creator_role() == has_creator_role
    assert user.has_guest_role() == has_guest_role
    assert user.is_creator() == is_creator
    assert user.is_guest() == is_guest
    assert user.is_player() == is_player

  def test_check_activation(self):
    user = factories.UserFactory(is_active=False)
    user.activation()

    assert user.is_active

  @pytest.mark.parametrize([
    'params',
    'default_email',
    'expected',
  ], [
    ({}, None, None),
    ({}, 'no-reply@led.quiz.com', 'no-reply@led.quiz.com'),
    ({'from_email': 'hoge@example.com'}, 'no-reply@led.quiz.com', 'hoge@example.com'),
  ], ids=[
    'params-is-empty',
    'use-default-email',
    'from_email-is-assigned',
  ])
  def test_check_send_email(self, settings, mocker, params, default_email, expected):
    settings.DEFAULT_FROM_EMAIL = default_email
    sender_mock = mocker.patch('account.models.EmailMessage.__init__', return_value=None)
    mocker.patch('account.models.EmailMessage.send', return_value=None)
    user = factories.UserFactory()
    # Define positional arguments
    subject = 'test-subject'
    message = 'test message in pytest'
    user.email_user(subject, message, **params)
    args, kwargs = sender_mock.call_args
    keys = kwargs.keys()

    if params.get('from_email'):
      callback = lambda items: items[0] == expected
    elif default_email:
      callback = lambda items: items[0] == default_email
    else:
      callback = lambda items: items is None

    assert sender_mock.call_count == 1
    assert args[0] == subject
    assert args[1] == message
    assert 'from_email' in keys
    assert 'to' in keys
    assert 'reply_to' in keys
    assert kwargs['from_email'] == params.get('from_email', default_email)
    assert isinstance(kwargs['to'], list)
    assert len(kwargs['to']) == 1
    assert kwargs['to'][0] == user.email
    assert callback(kwargs['reply_to'])

  def test_check_send_email_exception(self, mocker):
    class DummyLogger:
      def __init__(self):
        self.message = ''
      def error(self, message):
        self.message = message
    # Define test code
    mocker.patch('account.models.EmailMessage.send', side_effect=Exception('Failed'))
    mock_logger = mocker.patch('account.models.getLogger', return_value=DummyLogger())
    user = factories.UserFactory()
    # Call target method
    subject = 'test-subject'
    message = 'test message in pytest'
    user.email_user(subject, message)
    message = mock_logger.return_value.message

    assert message == f'Failed to send email to {user.email}'

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
  def test_check_change_role(self, role, expected):
    user = factories.UserFactory(role=role)
    user.update_role()

    assert user.role == expected

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
  def test_superuser_is_not_staffuser(self, options, err_msg):
    with pytest.raises(ValueError) as ex:
      _ = models.User.objects.create_superuser(
        email='hoge@foo.bar',
        **options,
      )
    assert err_msg in ex.value.args

  def test_empty_email(self):
    err_msg = 'The given email must be set.'

    with pytest.raises(ValueError) as ex:
      _ = models.User.objects.create_user(email='')
    assert err_msg in ex.value.args

  @pytest.mark.parametrize([
    'options',
  ], [
    ({'email': '{}@ng.com'.format('1'*122)},),
    ({'code': '1'*23},),
    ({'screen_name': '1'*129},),
    ({'password': f_pystr(min_chars=129,max_chars=129)},),
  ], ids=[
    'invalid-email',
    'invalid-code',
    'invalid-screen-name',
    'invalid-password',
  ])
  def test_check_invalid_input(self, options):
    with pytest.raises(DataError):
      user = factories.UserFactory.build(**options)
      user.save()

  def test_invalid_same_email(self):
    email = 'hoge@foo.example'
    valid_user = factories.UserFactory(email=email)

    with pytest.raises(IntegrityError):
      invalid_user = factories.UserFactory.build(email=email)
      invalid_user.save()

  def test_check_manager_collect_valid_normal_users(self):
    queryset = models.User.objects.collect_valid_normal_users()
    exacts = models.User.objects.filter(is_active=True, is_staff=False).exclude(role=models.RoleType.MANAGER)
    ids = list(queryset.values_list('pk', flat=True))

    assert queryset.count() == exacts.count()
    assert all([instance.pk in ids for instance in queryset])

  def test_check_queryset_collect_valid_normal_users(self):
    valid_users = factories.UserFactory.create_batch(3, is_active=True)
    all_users = [
      factories.UserFactory(is_active=True, is_staff=True, is_superuser=True),
      factories.UserFactory(is_active=True, is_staff=True),
      *factories.UserFactory.create_batch(2, is_active=False),
    ] + list(valid_users)
    queryset = models.User.objects.filter(pk__in=list(map(lambda val: val.pk, all_users))).collect_valid_normal_users()
    pks = [user.pk for user in valid_users]

    assert queryset.count() == len(pks)
    assert all([queryset.filter(pk=pk).exists() for pk in pks])

  def test_check_manager_collect_creators(self):
    queryset = models.User.objects.collect_creators()
    exacts = models.User.objects.filter(is_active=True, is_staff=False, role=models.RoleType.CREATOR)
    ids = list(queryset.values_list('pk', flat=True))

    assert queryset.count() == exacts.count()
    assert all([instance.pk in ids for instance in queryset])

  def test_check_manager_collect_valid_creators(self):
    queryset = models.User.objects.collect_valid_creators()
    exacts = models.User.objects.annotate(qc=Count('quizzes', filter=Q(quizzes__is_completed=True))) \
                                .filter(is_active=True, is_staff=False, role=models.RoleType.CREATOR, qc__gt=0)
    ids = list(queryset.values_list('pk', flat=True))

    assert queryset.count() == exacts.count()
    assert all([instance.pk in ids for instance in queryset])

  def test_check_queryset_collect_creators(self):
    all_users = []
    valid_users = []

    for idx, role in enumerate([models.RoleType.GUEST, models.RoleType.CREATOR, models.RoleType.MANAGER], 2):
      targets = list(factories.UserFactory.create_batch(idx, is_active=True, role=role))
      all_users += [
        factories.UserFactory(is_active=True, is_staff=True, is_superuser=True, role=role),
        factories.UserFactory(is_active=True, is_staff=True, role=role),
        *factories.UserFactory.create_batch(2, is_active=False, role=role),
      ] + targets

      if role == models.RoleType.CREATOR:
        valid_users += targets

    queryset = models.User.objects.filter(pk__in=list(map(lambda val: val.pk, all_users))).collect_creators()
    pks = [user.pk for user in valid_users]

    assert queryset.count() == len(pks)
    assert all([queryset.filter(pk=pk).exists() for pk in pks])

  @pytest.mark.parametrize([
    'is_completed',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'with-complated-quiz',
    'without-complated-quiz',
  ])
  def test_check_queryset_collect_valid_creators(self, is_completed):
    all_users = []
    valid_users = []
    genre = factories.GenreFactory(is_enabled=True)

    for idx, role in enumerate([models.RoleType.GUEST, models.RoleType.CREATOR, models.RoleType.MANAGER], 2):
      targets = list(factories.UserFactory.create_batch(idx, is_active=True, role=role))
      all_users += [
        factories.UserFactory(is_active=True, is_staff=True, is_superuser=True, role=role),
        factories.UserFactory(is_active=True, is_staff=True, role=role),
        *factories.UserFactory.create_batch(2, is_active=False, role=role),
      ] + targets

      if role == models.RoleType.CREATOR:
        for _user in targets:
          _ = factories.QuizFactory(creator=_user, genre=genre, is_completed=is_completed)

        if is_completed:
          valid_users += targets

    queryset = models.User.objects.filter(pk__in=list(map(lambda val: val.pk, all_users))).collect_valid_creators()
    pks = [user.pk for user in valid_users]

    assert queryset.count() == len(pks)
    assert all([queryset.filter(pk=pk).exists() for pk in pks])

  def test_check_get_response_kwargs(self, mocker):
    users = factories.UserFactory.create_batch(3, is_active=True, role=models.RoleType.CREATOR)
    users = models.User.objects.filter(pk__in=[obj.pk for obj in users]).order_by('pk')
    mocker.patch('account.models.User.objects.collect_creators', return_value=users)
    kwargs = models.User.get_response_kwargs('foobar')
    keys = kwargs.keys()

    assert 'rows' in keys
    assert 'header' in keys
    assert 'filename' in keys
    assert len(list(kwargs['rows'])) == len(users)
    assert all([
      all([item[0] == str(exact.pk), item[1] == str(exact), item[2] == exact.code])
      for item, exact in zip(list(kwargs['rows']), users)
    ])
    assert len(kwargs['header']) == 3
    assert kwargs['filename'] == 'creator-foobar.csv'

# =================
# = Role Approval =
# =================
@pytest.mark.account
@pytest.mark.model
@pytest.mark.django_db
class TestRoleApproval:
  def test_check_conducted_role_approval(self):
    user, other = factories.UserFactory.create_batch(2)
    _ = factories.RoleApprovalFactory(user=user, is_completed=False)

    assert user.conducted_role_approval()
    assert not other.conducted_role_approval()

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
  def test_check_collect_targets(self, completes, expected):
    users = factories.UserFactory.create_batch(len(completes))
    # Create approval requests
    for user, is_completed in zip(users, completes):
      _ = factories.RoleApprovalFactory(user=user, is_completed=is_completed)
    totals = models.RoleApproval.objects.collect_targets().count()

    assert totals == expected

  def test_check_str(self):
    user = factories.UserFactory()
    instance = factories.RoleApprovalFactory(user=user)

    assert str(instance) == str(user)

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
  def test_check_has_request_permission(self, role, requested, expected):
    user = factories.UserFactory(role=role)

    if requested:
      _ = factories.RoleApprovalFactory(user=user, is_completed=False)

    assert models.RoleApproval.has_request_permission(user) == expected

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
  def test_check_update_record(self, role, email, expected_email, expected_status):
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
class TestIndividualGroup:
  def test_valid_friends_change(self):
    friends = list(factories.UserFactory.create_batch(5, is_active=True))
    user = factories.UserFactory(is_active=True, friends=friends)
    instance = factories.IndividualGroupFactory(owner=user, members=[friends[1], friends[2]])
    # Define new friends by removing the first friend (friends[0])
    new_friends = models.User.objects.filter(pk__in=[user.pk for user in friends[1:]])
    rest_friends = instance.extract_invalid_friends(new_friends)

    assert rest_friends.count() == 0

  def test_invalid_friends_change(self):
    friends = list(factories.UserFactory.create_batch(5, is_active=True))
    user = factories.UserFactory(is_active=True, friends=friends)
    instance = factories.IndividualGroupFactory(owner=user, members=[friends[1], friends[2]])
    # Define new friends by removing the second friend (friends[1]) and the last friend (friends[-1])
    new_friends = models.User.objects.filter(pk__in=[friends[0].pk, friends[2].pk, friends[3].pk])
    rest_friends = instance.extract_invalid_friends(new_friends)

    assert rest_friends.count() == 1
    assert str(rest_friends[0].pk) == str(friends[1].pk)

  def test_invalid_members(self):
    friends = list(factories.UserFactory.create_batch(3))
    _other = factories.UserFactory()
    owner = factories.UserFactory(friends=friends)
    instance = factories.IndividualGroupFactory(owner=owner, members=[_other, *friends])
    # Call target method
    input_friends = models.User.objects.filter(pk__in=[user.pk for user in friends])
    invalid = instance.exists_invalid_members(instance.members, input_friends)

    assert invalid

  @pytest.mark.parametrize([
    'friend_indices',
    'rest_count',
  ], [
    ([0, 1, 2], 0),
    ([0, 2, 3], 1),
  ], ids=[
    'vaild-friends',
    'invalid-friends',
  ])
  def test_invalid_friends(self, friend_indices, rest_count):
    friends = list(factories.UserFactory.create_batch(5, is_active=True))
    # Define the specific friends given by `friend_indices`
    user = factories.UserFactory(is_active=True, friends=[friends[idx] for idx in friend_indices])
    instance = factories.IndividualGroupFactory(owner=user, members=[friends[1], friends[2]])
    rest_friends = instance.extract_invalid_friends()

    assert rest_friends.count() == rest_count

  @pytest.fixture(params=['valid-pattern', 'invalid-owner-pk', 'not-exist-owner', 'invalid-group-pk', 'not-exist-group'], scope='class')
  def get_argument_patterns(self, request, django_db_blocker):
    with django_db_blocker.unblock():
      _ = factories.UserFactory(is_active=True, is_staff=True, is_superuser=True)
      _ = factories.UserFactory(is_active=True, is_staff=True)
      _ = factories.UserFactory(is_active=True, role=models.RoleType.MANAGER)
      _ = factories.UserFactory(is_active=True, role=models.RoleType.CREATOR)
      nobody = factories.UserFactory(is_active=True)
      members = list(factories.UserFactory.create_batch(3, is_active=True))
      user = factories.UserFactory(is_active=True, friends=members)
      group = factories.IndividualGroupFactory(owner=user, members=[members[0], members[-1]])
      someone = list(factories.UserFactory.create_batch(2, is_active=True))
      other = factories.UserFactory(is_active=True, friends=someone)
      _other_group = factories.IndividualGroupFactory(owner=other, members=[someone[0]])
      not_exist_group = factories.IndividualGroupFactory(owner=other, members=someone)
      nobody.delete()
      not_exist_group.delete()
      _specific = g_generate_item([members[0], members[-1]], False)
      _all = g_generate_item(models.User.objects.collect_valid_normal_users(), False)
    # Define patterns
    patterns = {
      'valid-pattern':    ({'owner': user,   'group_pk':           group.pk}, _specific),
      'invalid-owner-pk': ({'owner': nobody, 'group_pk':           group.pk}, _all),
      'not-exist-owner':  ({'owner': user,   'group_pk':    _other_group.pk}, _all),
      'invalid-group-pk': ({'owner': user,   'group_pk': not_exist_group.pk}, _all),
      'not-exist-group':  ({'owner': other,  'group_pk':           group.pk}, _all),
    }
    kwargs, exact_arr = patterns[request.param]

    return kwargs, exact_arr

  def test_check_get_options(self, get_argument_patterns):
    # Get arguments
    kwargs, exact_arr = get_argument_patterns
    options = models.IndividualGroup.get_options(**kwargs)

    assert g_compare_options(options, exact_arr)