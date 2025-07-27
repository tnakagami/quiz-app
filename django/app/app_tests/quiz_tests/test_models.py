import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError, DataError
from app_tests import (
  factories,
  g_generate_item,
  g_compare_options,
)
from account.models import RoleType
from quiz import models

UserModel = get_user_model()

class Common:
  pk_convertor = lambda _self, xs: [item.pk for item in xs]

  @pytest.fixture(scope='module', params=[
    'superuser-manager',
    'superuser-creator',
    'superuser-guest',
    'staff-manager',
    'staff-creator',
    'staff-guest',
    'normal-manager',
    'normal-creator',
    'normal-guest',
    'not-active',
  ], ids=lambda xs: str(xs))
  def get_user(self, django_db_blocker, request):
    with django_db_blocker.unblock():
      _user_table = {
        'superuser-manager': factories.UserFactory(is_active=True, is_staff=True, is_superuser=True, role=RoleType.MANAGER),
        'superuser-creator': factories.UserFactory(is_active=True, is_staff=True, is_superuser=True, role=RoleType.CREATOR),
        'superuser-guest': factories.UserFactory(is_active=True, is_staff=True, is_superuser=True, role=RoleType.GUEST),
        'staff-manager': factories.UserFactory(is_active=True, is_staff=True, role=RoleType.MANAGER),
        'staff-creator': factories.UserFactory(is_active=True, is_staff=True, role=RoleType.CREATOR),
        'staff-guest': factories.UserFactory(is_active=True, is_staff=True, role=RoleType.GUEST),
        'normal-manager': factories.UserFactory(is_active=True, role=RoleType.MANAGER),
        'normal-creator': factories.UserFactory(is_active=True, role=RoleType.CREATOR),
        'normal-guest': factories.UserFactory(is_active=True, role=RoleType.GUEST),
        'not-active': factories.UserFactory(is_active=False),
      }
    key = request.param
    user = _user_table[key]

    return key, user

# =========
# = Genre =
# =========
@pytest.mark.quiz
@pytest.mark.model
@pytest.mark.django_db
class TestGenre(Common):
  def test_check_instance_type(self):
    genre = factories.GenreFactory.build()

    assert isinstance(genre, models.Genre)

  @pytest.mark.parametrize([
    'name',
    'is_enabled',
  ], [
    ('hoge', True),
    ('foo', False),
  ], ids=lambda xs: str(xs))
  def test_create_instance(self, name, is_enabled):
    instance = models.Genre.objects.create(name=name, is_enabled=is_enabled)

    assert instance.name == name
    assert instance.is_enabled == is_enabled
    assert str(instance) == name

  def test_check_validation(self):
    with pytest.raises(DataError):
      instance = factories.GenreFactory.build(name='1'*129)
      instance.save()

  def test_check_same_name(self):
    name = 'hoge'
    _ = factories.GenreFactory(name=name)

    with pytest.raises(IntegrityError):
      instance = factories.GenreFactory.build(name=name)
      instance.save()

  @pytest.mark.parametrize([
    'role',
    'is_valid',
  ], [
    (RoleType.MANAGER, True),
    (RoleType.CREATOR, False),
    (RoleType.GUEST, False),
  ], ids=[
    'is-manager',
    'is-creator',
    'is-guest',
  ])
  def test_check_update_permission_based_on_role(self, get_genres, role, is_valid):
    user = factories.UserFactory(is_active=True, role=role)
    instance = get_genres[0]

    assert instance.has_update_permission(user) == is_valid

  def test_check_update_permission_from_user_pattern(self, get_genres, get_user):
    _, user = get_user
    instance = get_genres[0]

    assert not instance.has_delete_permission(user)

  def test_check_active_genres(self):
    genres = factories.GenreFactory.create_batch(4, is_enabled=False)
    genres[1].is_enabled = True
    genres[1].save()
    genres[2].is_enabled = True
    genres[2].save()
    queryset = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).collect_active_genres()
    pk1 = genres[1].pk
    pk2 = genres[2].pk

    assert queryset.count() == 2
    assert queryset.filter(pk__in=[pk1]).exists()
    assert queryset.filter(pk__in=[pk2]).exists()

  @pytest.mark.parametrize([
    'is_completed',
    'count',
    'callback',
  ], [
    (True, 2, lambda qs, exacts: all([qs.filter(pk__in=[pk]).exists() for pk in exacts])),
    (False, 0, lambda qs, exacts: True),
  ], ids=[
    'completed-quiz',
    'not-completed-quiz',
  ])
  def test_check_valid_genres(self, is_completed, count, callback):
    creator = factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    genres = factories.GenreFactory.create_batch(4, is_enabled=False)
    genres[1].is_enabled = True
    genres[1].save()
    genres[2].is_enabled = True
    genres[2].save()

    for genre in genres:
      _ = factories.QuizFactory(creator=creator, genre=genre, is_completed=is_completed)
    queryset = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).collect_valid_genres()
    exacts = [
      genres[1].pk,
      genres[2].pk,
    ]

    assert queryset.count() == count
    assert callback(queryset, exacts)

  @pytest.mark.parametrize([
    'row',
    'is_valid',
  ], [
    ([1, ], True),
    ([1, 2], False),
  ], ids=[
    'length-is-1',
    'length-is-2',
  ])
  def test_check_length_checker(self, row, is_valid):
    assert models.Genre.length_checker(row) == is_valid

  def test_valid_records_by_using_record_checker(self, mocker):
    genres = [
      factories.GenreFactory(name='hoge00-012', is_enabled=True),
      factories.GenreFactory(name='foobar-123', is_enabled=True),
      factories.GenreFactory(name='xyzw01-234', is_enabled=True),
    ]
    rows = [['valid-01',], ['valid-02',], ['valid-03',]]
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres))
    mocker.patch('quiz.models.Genre.objects.collect_active_genres', return_value=genres)
    is_valid, err = models.Genre.record_checker(rows)

    assert is_valid
    assert err is None

  def test_invalid_records_by_using_record_checker(self, mocker):
    genres = [
      factories.GenreFactory(name='hoge00-012', is_enabled=True),
      factories.GenreFactory(name='foobar-123', is_enabled=True),
      factories.GenreFactory(name='xyzw01-234', is_enabled=True),
      factories.GenreFactory(name='invalid-99', is_enabled=True),
    ]
    pk1, pk3 = genres[1].pk, genres[3].pk
    rows = [['valid-01',], ['foobar-123',], ['invalid-99',]]
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres))
    mocker.patch('quiz.models.Genre.objects.all', return_value=genres)
    # Define error message
    invalids = models.Genre.objects.filter(pk__in=[pk1, pk3]).order_by('name')
    msg = ','.join([str(_genre) for _genre in invalids])
    exact_err = f'The csv file includes invalid genre(s). Details: {msg}'
    # Raise exception
    with pytest.raises(ValidationError) as ex:
      is_valid, err = models.Genre.record_checker(rows)
      raise err

    assert not is_valid
    assert exact_err in str(ex.value)

  @pytest.mark.parametrize([
    'rows',
    'expected',
  ], [
    ([('valid-01',), ('valid-02',), ('valid-03',)], ['valid-01', 'valid-02', 'valid-03']),
    ([('valid-01',), ('valid-02',), ('valid-03',), ('valid-02',), ('valid-01',)], ['valid-01', 'valid-02', 'valid-03']),
  ], ids=[
    'unique-list',
    'duplication-list',
  ])
  def test_check_get_instances_from_list_method(self, rows, expected):
    instances = models.Genre.get_instances_from_list(rows)

    assert len(instances) == len(expected)
    assert all([obj.name in expected for obj in instances])
    assert all([obj.is_enabled for obj in instances])

  def test_check_get_response_kwargs_method(self, mocker, get_genres):
    genres = get_genres
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).order_by('name')
    mocker.patch('quiz.models.Genre.objects.collect_active_genres', return_value=genres)
    kwargs = models.Genre.get_response_kwargs('foobar')
    keys = kwargs.keys()

    assert 'rows' in keys
    assert 'header' in keys
    assert 'filename' in keys
    assert len(list(kwargs['rows'])) == len(genres)
    assert all([item.pk == exact.pk for item, exact in zip(kwargs['rows'], genres)])
    assert len(kwargs['header']) == 1
    assert kwargs['filename'] == 'genre-foobar.csv'

# ========
# = Quiz =
# ========
@pytest.mark.quiz
@pytest.mark.model
@pytest.mark.django_db
class TestQuiz(Common):
  def test_check_instance_type(self):
    quiz = factories.QuizFactory.build()

    assert isinstance(quiz, models.Quiz)

  @pytest.mark.parametrize([
    'question',
    'answer',
    'is_completed',
    'short_question',
    'short_answer',
  ], [
    ('hogehoge', 'foobar', False, 'hogehoge', 'foobar'),
    ('01234'*4, 'abcd'*5, True, '0123401234012340', 'abcdabcdabcdabcd'),
    (None, None, True, '(Not set)', '(Not set)'),
  ], ids=[
    'normal-quiz',
    'too-long-quiz',
    'not-set',
  ])
  def test_create_instance(self, get_genres, question, answer, is_completed, short_question, short_answer):
    kwargs = {
      'question': question,
      'answer': answer,
      'is_completed': is_completed,
    }
    if question is None:
      del kwargs['question']
      exact_question = ''
    else:
      exact_question = question
    if answer is None:
      del kwargs['answer']
      exact_answer = ''
    else:
      exact_answer = answer
    # Create instance
    user = factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    genre = get_genres[0]
    instance = models.Quiz.objects.create(
      creator=user,
      genre=genre,
      **kwargs,
    )
    str_val = f'{short_question}({user})'

    assert instance.creator.pk == user.pk
    assert instance.genre.pk == genre.pk
    assert instance.question == exact_question
    assert instance.answer == exact_answer
    assert instance.is_completed == is_completed
    assert str(instance) == str_val
    assert instance.get_short_question() == short_question
    assert instance.get_short_answer() == short_answer

  @pytest.mark.parametrize([
    'kwargs',
    'expected',
  ], [
    ({'sentence': 'hoge'}, 'hoge'),
    ({'sentence': f"{'1'*15}2"}, f"{'1'*15}2"),
    ({'sentence': f"{'1'*15}23"}, f"{'1'*15}2"),
    ({'sentence': 'hogehoge', 'max_length': 3}, 'hog'),
  ], ids=[
    'is-normal',
    'length-is-16',
    'length-is-17',
    'length-is-3',
  ])
  def test_splittext_method(self, kwargs, expected):
    instance = factories.QuizFactory()
    out = instance._split_text(**kwargs)

    assert out == expected

  @pytest.fixture(scope='class')
  def get_quizzes_info(self, django_db_blocker, get_genres):
    with django_db_blocker.unblock():
      creators = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.CREATOR)
      genres = get_genres[:4]
      # Create quiz
      for creator in creators:
        for genre in genres:
          _ = factories.QuizFactory(creator=creator, genre=genre, is_completed=True)
      models.Quiz.objects.filter(creator=creators[0], genre=genres[2]).update(is_completed=False)

    return creators, genres

  @pytest.mark.parametrize([
    'input_type',
    'expected_type',
  ], [
    ('no-args', 'completed-records'),
    ('only-creator', 'creator-record'),
    ('only-genre', 'genre-record'),
    ('both', 'specific-records'),
    ('one-creator', 'creator-record'),
    ('one-genre', 'genre-record'),
    ('two-creators-list', 'creators-result'),
    ('two-genres-list', 'genres-result'),
  ], ids=[
    'no-filtering-condition',
    'set-only-one-creator',
    'set-only-one-genre',
    'set-many-creators-and-genres',
    'set-one-creator',
    'set-one-genre',
    'set-two-creators-with-list',
    'set-two-genres-with-list',
  ])
  def test_collect_quizzes_queryset(self, get_quizzes_info, input_type, expected_type):
    creators, genres = get_quizzes_info
    # Create patterns and exact values
    patterns = {
      'no-args': {},
      'only-creator': {'creators': UserModel.objects.filter(pk__in=[creators[0].pk])},
      'only-genre': {'genres': models.Genre.objects.filter(pk__in=[genres[0].pk])},
      'both': {
        'creators': UserModel.objects.exclude(pk__in=[creators[0].pk]),
        'genres': models.Genre.objects.exclude(pk__in=[genres[0].pk]),
      },
      'one-creator': {'creators': creators[0]},
      'one-genre': {'genres': genres[0]},
      'two-creators-list': {'creators': [creators[0], creators[2]]},
      'two-genres-list': {'genres': [genres[0], genres[1]]},
    }
    exacts = {
      'completed-records': models.Quiz.objects.filter(is_completed=True),
      'creator-record': models.Quiz.objects.filter(is_completed=True, creator=creators[0]),
      'genre-record': models.Quiz.objects.filter(is_completed=True, genre=genres[0]),
      'specific-records': models.Quiz.objects.filter(is_completed=True).exclude(creator=creators[0], genre=genres[0]),
      'creators-result': models.Quiz.objects.filter(is_completed=True, creator__pk__in=[creators[0].pk, creators[2].pk]),
      'genres-result': models.Quiz.objects.filter(is_completed=True, genre__pk__in=[genres[0].pk, genres[1].pk]),
    }
    # Call collect_quizzes method
    kwargs = patterns[input_type]
    expected = list(exacts[expected_type].values_list('pk', flat=True))
    queryset = models.Quiz.objects.collect_quizzes(**kwargs)
    ids = queryset.values_list('pk', flat=True)

    assert len(expected) == len(ids)
    assert all([pk in expected for pk in ids])

  @pytest.mark.parametrize([
    'user_type',
    'can_update',
  ], [
    ('owner', True),
    ('superuser', True),
    ('manager', True),
    ('creator', False),
    ('guest', False),
  ], ids=[
    'is-owner',
    'is-superuser',
    'is-manager',
    'is-creator',
    'is-guest',
  ])
  def test_has_update_permission(self, user_type, can_update):
    owner = factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    instance = factories.QuizFactory(creator=owner)
    # Create pattern
    patterns = {
      'owner': owner,
      'superuser': factories.UserFactory(is_active=True, is_staff=True, is_superuser=True, role=RoleType.GUEST),
      'manager': factories.UserFactory(is_active=True, role=RoleType.MANAGER),
      'creator': factories.UserFactory(is_active=True, role=RoleType.CREATOR),
      'guest': factories.UserFactory(is_active=True, role=RoleType.GUEST),
    }
    user = patterns[user_type]

    assert can_update == instance.has_update_permission(user)

  @pytest.mark.parametrize([
    'row',
    'is_valid',
  ], [
    ([1, 2, 3, 4, 5], True),
    ([1, 2, 3, 4], False),
  ], ids=[
    'length-is-5',
    'length-is-4',
  ])
  def test_check_length_checker(self, row, is_valid):
    assert models.Quiz.length_checker(row) == is_valid

  @pytest.mark.parametrize([
    'row',
  ], [
    ([1, 2], ),
    ([2, 3, 4], ),
  ], ids=[
    'only-two-data',
    'more-than-two-data',
  ])
  def test_check_record_extractor(self, row):
    out = models.Quiz.record_extractor(row)

    assert out[0] == row[0]
    assert out[1] == row[1]

  @pytest.mark.parametrize([
    'has_manager_role',
    'indices',
  ], [
    #       creator
    #         | genre
    #         |  |
    #         V  V
    (False, [(0, 1), (0, 2), (0, 0)]),
    (True,  [(1, 2), (0, 3), (1, 0), (0, 1)]),
  ], ids=[
    'is-creator',
    'is-manager',
  ])
  def test_valid_records_by_using_record_checker(self, mocker, get_quizzes_info, has_manager_role, indices):
    creators, genres = get_quizzes_info
    user = creators[0] if not has_manager_role else factories.UserFactory(is_active=True, role=RoleType.MANAGER)
    rows = [(str(creators[c_idx].pk), genres[g_idx].name) for c_idx, g_idx in indices]
    creators = UserModel.objects.filter(pk__in=self.pk_convertor(creators))
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres))
    mocker.patch('quiz.models.UserModel.objects.collect_creators', return_value=creators)
    mocker.patch('quiz.models.Genre.objects.collect_active_genres', return_value=genres)
    is_valid, err = models.Quiz.record_checker(rows, user)

    assert is_valid
    assert err is None

  @pytest.mark.parametrize([
    'has_manager_role',
    'indices',
    'is_invalid_genre',
    'invalid_indices',
  ], [
    (False, [(0, 1), (0, 3), ( 0, -1), ( 0, 2)],  True, [-1]),
    (False, [(0, 1), (0, 3), ( 0,  0), (-1, 2)], False, [-1]),
    (False, [(0, 1), (0, 3), ( 1,  0), ( 2, 2)], False, [1, 2]),
    (True,  [(0, 1), (0, 3), ( 0, -1), ( 0, 2)],  True, [-1]),
    (True,  [(0, 1), (0, 3), ( 0,  0), (-1, 2)], False, [-1]),
    (True,  [(0, 1), (0, 3), (-2,  0), (-2, 2)], False, [-2]),
  ], ids=[
    'creator-with-invalid-genre',
    'creator-with-guest',
    'creator-with-other-creator',
    'is-manager-with-invalid-genre',
    'is-manager-with-guest',
    'is-manager-with-invalid-creator',
  ])
  def test_invalid_records_by_using_record_checker(self, mocker, get_quizzes_info, has_manager_role, indices, is_invalid_genre, invalid_indices):
    creators, genres = get_quizzes_info
    _invalid_genres = list(genres) + [factories.GenreFactory(is_enabled=False)]
    _invalid_creators = list(creators) + [
      factories.UserFactory(is_active=False, role=RoleType.CREATOR),
      factories.UserFactory(is_active=True, role=RoleType.GUEST),
    ]
    user = creators[0] if not has_manager_role else factories.UserFactory(is_active=True, role=RoleType.MANAGER)
    rows = [(str(_invalid_creators[c_idx].pk), _invalid_genres[g_idx].name) for c_idx, g_idx in indices]
    creators = UserModel.objects.filter(pk__in=self.pk_convertor(creators))
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres))
    mocker.patch('quiz.models.UserModel.objects.collect_creators', return_value=creators)
    mocker.patch('quiz.models.Genre.objects.collect_active_genres', return_value=genres)
    # Create exact data
    if is_invalid_genre:
      invalids = models.Genre.objects.filter(pk__in=self.pk_convertor([_invalid_genres[idx] for idx in invalid_indices])).order_by('name')
      msg = ','.join([str(_genre) for _genre in invalids])
      exact_err = f'The csv file includes invalid genre(s). Details: {msg}'
    else:
      invalids = UserModel.objects.filter(pk__in=self.pk_convertor([_invalid_creators[idx] for idx in invalid_indices])).order_by('pk')
      msg = ','.join([str(_creator) for _creator in invalids])
      exact_err = f'The csv file includes invalid creator(s). Details: {msg}'
    # Raise exception
    with pytest.raises(ValidationError) as ex:
      is_valid, err = models.Quiz.record_checker(rows, user)
      raise err

    assert not is_valid
    assert exact_err in str(ex.value)

  @pytest.mark.parametrize([
    'role',
    'rows',
  ], [
    (RoleType.MANAGER, [('invalid-c-pk', 'invalid-g-name')]),
    (RoleType.CREATOR, [('invalid-c-pk', 'invalid-g-name')]),
    (RoleType.MANAGER, []),
    (RoleType.CREATOR, []),
  ], ids=[
    'is-manager-with-a-record',
    'is-creator-with-a-record',
    'is-manager-without-records',
    'is-creator-without-records',
  ])
  def test_include_non_uuid_record(self, role, rows):
    user = factories.UserFactory(is_active=True, role=role)

    with pytest.raises(ValidationError) as ex:
      is_valid, err = models.Quiz.record_checker(rows, user)
      raise err

    assert not is_valid
    assert 'The csv file includes invalid value(s).' in str(ex.value)

  def test_check_get_instance_from_list_method(self, get_quizzes_info):
    creators, genres = get_quizzes_info
    _creator = creators[0]
    _genre = genres[0]
    row = [
      str(_creator.pk),
      _genre.name,
      'hogehoge-quiz',
      'fugafuga-answer',
      'true',
    ]
    instance = models.Quiz.get_instance_from_list(row)

    assert instance.creator.pk == _creator.pk
    assert instance.genre.pk == _genre.pk
    assert instance.question == 'hogehoge-quiz'
    assert instance.answer == 'fugafuga-answer'
    assert instance.is_completed

  def test_check_get_response_kwargs_method(self, get_quizzes_info):
    creators, _ = get_quizzes_info
    ids = creators[0].quizzes.all().order_by('genre__name', 'creator__screen_name').values_list('pk', flat=True)
    kwargs = models.Quiz.get_response_kwargs('hoge', ids)
    keys = kwargs.keys()

    assert 'rows' in keys
    assert 'header' in keys
    assert 'filename' in keys
    assert len(list(kwargs['rows'])) == len(ids)
    assert all([item.pk == exact for item, exact in zip(kwargs['rows'], ids)])
    assert len(kwargs['header']) == 5
    assert kwargs['filename'] == 'quiz-hoge.csv'

  @pytest.mark.parametrize([
    'has_manager_role',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'is-manager',
    'is-creator',
  ])
  def test_get_quizzes_based_on_userpk(self, mocker, get_quizzes_info, has_manager_role):
    creators, _ = get_quizzes_info
    quizzes = models.Quiz.objects.filter(creator__pk__in=self.pk_convertor(creators))
    mocker.patch('quiz.models.Quiz.objects.select_related', return_value=quizzes)
    # Define expected content
    if has_manager_role:
      user = factories.UserFactory(is_active=True, role=RoleType.MANAGER)
      use_qs = quizzes
    else:
      user = creators[0]
      use_qs = quizzes.filter(creator=user)
    expected = [
      {
        'pk': str(instance.pk),
        'creator': str(instance.creator),
        'genre': str(instance.genre),
        'question': instance.get_short_question(),
        'answer': instance.get_short_answer(),
        'is_completed': instance.is_completed,
      }
      for instance in use_qs.order_by('pk')
    ]
    # Call target method
    estimated = models.Quiz.get_quizzes(user)
    keys = ['pk', 'creator', 'genre', 'question', 'answer', 'is_completed']

    assert len(estimated) == len(expected)
    assert all([all([val[key] == exact[key] for key in keys]) for val, exact in zip(estimated, expected)])

# ============
# = QuizRoom =
# ============
@pytest.mark.quiz
@pytest.mark.model
@pytest.mark.django_db
class TestQuizRoom(Common):
  def test_check_instance_type(self):
    owner = factories.UserFactory(is_active=True, screen_name='hoge')
    room = factories.QuizRoomFactory.build(owner=owner, name='foo')
    str_val = 'foo(hoge)'

    assert isinstance(room, models.QuizRoom)
    assert str(room) == str_val

  def test_check_validation(self):
    with pytest.raises(DataError):
      instance = factories.QuizRoomFactory.build(name='1'*129)
      instance.save()

  def test_call_collect_relevant_room_by_manager(self):
    user = factories.UserFactory(is_active=True, role=RoleType.MANAGER)
    creator = factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    guest = factories.UserFactory(is_active=True, role=RoleType.GUEST)
    all_rooms = [
      *factories.QuizRoomFactory.create_batch(2, owner=guest, is_enabled=True),
      *factories.QuizRoomFactory.create_batch(3, owner=creator, is_enabled=True, members=[guest.pk]),
      *factories.QuizRoomFactory.create_batch(2, owner=creator, is_enabled=False),
    ]
    queryset = models.QuizRoom.objects.filter(pk__in=self.pk_convertor(all_rooms)).collect_relevant_rooms(user)
    ids = list(queryset.values_list('pk', flat=True))
    exacts = [room.pk for room in all_rooms]

    assert len(ids) == len(all_rooms)
    assert all([pk in exacts for pk in ids])

  def test_check_collect_relevant_room(self):
    user = factories.UserFactory(is_active=True, role=RoleType.GUEST)
    other = factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    can_use_rooms = [
      *factories.QuizRoomFactory.create_batch(3, owner=user, is_enabled=True),
      *factories.QuizRoomFactory.create_batch(2, owner=other, is_enabled=True, members=[user.pk]),
    ]
    cannot_use_rooms = factories.QuizRoomFactory.create_batch(2, owner=other, is_enabled=False)
    all_rooms = can_use_rooms + cannot_use_rooms
    queryset = models.QuizRoom.objects.filter(pk__in=self.pk_convertor(all_rooms)).collect_relevant_rooms(user)
    ids = list(queryset.values_list('pk', flat=True))
    exacts = [room.pk for room in can_use_rooms]

    assert len(ids) == len(can_use_rooms)
    assert all([pk in exacts for pk in ids])

  def test_check_is_assigned_method(self, get_user):
    key, user = get_user
    owner = factories.UserFactory(is_active=True)
    is_player = key in ['staff-creator', 'staff-guest', 'normal-creator', 'normal-guest', 'not-active']
    instance = factories.QuizRoomFactory(owner=owner, members=[user.pk], is_enabled=True)

    assert is_player == instance.is_assigned(user)

  @pytest.mark.parametrize([
    'is_enabled',
    'role',
  ], [
    (True, RoleType.GUEST),
    (True, RoleType.CREATOR),
    (False, RoleType.GUEST),
  ], ids=[
    'is-enabled-with-guest',
    'is-enabled-with-creator',
    'is-not-enabled-with-guest',
  ])
  def test_check_reset_method(self, is_enabled, role):
    genres = factories.GenreFactory.create_batch(4, is_enabled=True)
    creators = factories.UserFactory.create_batch(4, is_active=True, role=RoleType.CREATOR)
    members = factories.UserFactory.create_batch(6, is_active=True)
    members = UserModel.objects.filter(pk__in=self.pk_convertor(members)).order_by('pk')
    owner = factories.UserFactory(is_active=True, role=role)
    quizzes = [
      factories.QuizFactory(creator=creators[0], genre=genres[0], is_completed=True),  # 0
      factories.QuizFactory(creator=creators[0], genre=genres[1], is_completed=False), # 1, Is not selected
      factories.QuizFactory(creator=creators[1], genre=genres[0], is_completed=True),  # 2, Is not selected
      factories.QuizFactory(creator=creators[1], genre=genres[1], is_completed=True),  # 3
      factories.QuizFactory(creator=creators[2], genre=genres[1], is_completed=True),  # 4
      factories.QuizFactory(creator=creators[2], genre=genres[3], is_completed=True),  # 5, Is not selected
      factories.QuizFactory(creator=creators[3], genre=genres[0], is_completed=True),  # 6, Is not selected
      factories.QuizFactory(creator=creators[3], genre=genres[0], is_completed=True),  # 7, Is not selected
      factories.QuizFactory(creator=creators[3], genre=genres[2], is_completed=True),  # 8
    ]
    room = factories.QuizRoomFactory(
      owner=owner,
      creators=[creators[0]],
      genres=[genres[1], genres[2]],
      members=list(members),
      max_question=4,
      is_enabled=is_enabled,
    )
    room.score.status = models.QuizStatusType.ANSWERING
    room.score.index = 2
    room.score.sequence = {}
    room.score.detail = {}
    room.score.save()
    # Call target method
    room.reset()
    _expected_vals = {
      True: {
        'index': 1,
        'len_seq': room.max_question,
        'len_detail': len(members) + 1,
        'status': models.QuizStatusType.START,
        'seq': [str(quizzes[idx].pk) for idx in [0, 3, 4, 8]],
        'detail': [str(owner.pk)] + [str(pk) for pk in members.values_list('pk', flat=True)],
      },
      False: {
        'index': 2,
        'len_seq': 0,
        'len_detail': 0,
        'status': models.QuizStatusType.ANSWERING,
        'seq': [],
        'detail': [],
      },
    }
    expected = _expected_vals[is_enabled]

    assert room.score.index == expected['index']
    assert len(room.score.sequence) == expected['len_seq']
    assert len(room.score.detail) == expected['len_detail']
    assert room.score.status == expected['status']
    assert all([pk in expected['seq'] for pk in room.score.sequence.values()])
    assert all([pk in expected['detail'] for pk in room.score.detail.keys()])

  @pytest.mark.parametrize([
    'role',
    'is_enabled',
    'expected',
  ], [
    (RoleType.MANAGER, True, False),
    (RoleType.CREATOR, True, True),
    (RoleType.GUEST, True, True),
    (RoleType.MANAGER, False, False),
    (RoleType.CREATOR, False, False),
    (RoleType.GUEST, False, False),
  ], ids=[
    'is-manager-and-enable',
    'is-creator-and-enable',
    'is-guest-and-enable',
    'is-manager-and-disable',
    'is-creator-and-disable',
    'is-guest-and-disable',
  ])
  def test_validation_for_owner_and_enable_flag(self, role, is_enabled, expected):
    owner = factories.UserFactory(is_active=True, role=role)
    members = factories.UserFactory.create_batch(3, is_active=True)
    instance = factories.QuizRoomFactory(owner=owner, members=list(members), is_enabled=is_enabled)

    assert instance.is_assigned(owner) == expected
    assert instance.is_owner(owner)

  @pytest.mark.parametrize([
    'role',
    'is_creator',
  ], [
    (RoleType.MANAGER, False),
    (RoleType.CREATOR, True),
    (RoleType.GUEST, False),
  ], ids=[
    'is-manager',
    'is-creator',
    'is-guest',
  ])
  def test_check_creator_assignment(self, role, is_creator):
    users = factories.UserFactory.create_batch(2, is_active=True, role=RoleType.CREATOR)
    _user = factories.UserFactory(is_active=True, role=role)
    members = list(users) + [_user]

    assert is_creator == models.QuizRoom.is_only_creator(members)

  @pytest.mark.parametrize([
    'role',
    'is_player',
  ], [
    (RoleType.MANAGER, False),
    (RoleType.CREATOR, True),
    (RoleType.GUEST, True),
  ], ids=[
    'is-manager',
    'is-creator',
    'is-guest',
  ])
  def test_check_player_assignment(self, role, is_player):
    members = [
      factories.UserFactory(is_active=True, role=RoleType.GUEST),
      factories.UserFactory(is_active=True, role=RoleType.CREATOR),
      factories.UserFactory(is_active=True, role=role),
    ]

    assert is_player == models.QuizRoom.is_only_player(members)

  @pytest.mark.parametrize([
    'user_type',
    'can_update',
  ], [
    ('owner-creator', True),
    ('owner-guest', True),
    ('superuser', True),
    ('manager', True),
    ('creator', False),
    ('guest', False),
  ], ids=[
    'is-owner-of-creator',
    'is-owner-of-guest',
    'is-superuser',
    'is-manager',
    'is-creator',
    'is-guest',
  ])
  def test_check_update_permission(self, user_type, can_update):
    _role = RoleType.GUEST if user_type == 'owner-guest' else RoleType.CREATOR
    owner = factories.UserFactory(is_active=True, role=_role)
    instance = factories.QuizRoomFactory(owner=owner)
    # Create pattern
    patterns = {
      'owner-creator': owner,
      'owner-guest': owner,
      'superuser': factories.UserFactory(is_active=True, is_staff=True, is_superuser=True, role=RoleType.GUEST),
      'manager': factories.UserFactory(is_active=True, role=RoleType.MANAGER),
      'creator': factories.UserFactory(is_active=True, role=RoleType.CREATOR),
      'guest': factories.UserFactory(is_active=True, role=RoleType.GUEST),
    }
    user = patterns[user_type]

    assert can_update == instance.has_update_permission(user)

  @pytest.mark.parametrize([
    'user_type',
    'is_enabled',
    'can_delete',
  ], [
    ('owner-creator', True, False),
    ('owner-creator', False, True),
    ('owner-guest', True, False),
    ('owner-guest', False, True),
    ('manager', True, False),
    ('manager', False, True),
    ('creator', True, False),
    ('creator', False, False),
    ('guest', True, False),
    ('guest', False, False),
  ], ids=[
    'is-owner-of-creator-and-is-enabled',
    'is-owner-of-creator-and-is-not-enabled',
    'is-owner-of-guest-and-is-enabled',
    'is-owner-of-guest-and-is-not-enabled',
    'is-manager-and-is-enabled',
    'is-manager-and-is-not-enabled',
    'is-creator-and-is-enabled',
    'is-creator-and-is-not-enabled',
    'is-guest-and-is-enabled',
    'is-guest-and-is-not-enabled',
  ])
  def test_check_delete_permission(self, user_type, is_enabled, can_delete):
    _role = RoleType.GUEST if user_type == 'owner-guest' else RoleType.CREATOR
    owner = factories.UserFactory(is_active=True, role=_role)
    instance = factories.QuizRoomFactory(owner=owner, is_enabled=is_enabled)
    # Create pattern
    patterns = {
      'owner-creator': owner,
      'owner-guest': owner,
      'manager': factories.UserFactory(is_active=True, role=RoleType.MANAGER),
      'creator': factories.UserFactory(is_active=True, role=RoleType.CREATOR),
      'guest': factories.UserFactory(is_active=True, role=RoleType.GUEST),
    }
    user = patterns[user_type]

    assert can_delete == instance.has_delete_permission(user)

  @pytest.mark.parametrize([
    'names',
    'expected',
  ], [
    ([], '-'),
    (['hoge'], 'hoge'),
    (['foo', 'bar'], 'bar,foo'),
  ], ids=[
    'is-empty',
    'only-one-genre',
    'many-genres',
  ])
  def test_check_get_genres_method(self, names, expected):
    if names:
      kwargs = {
        'genres': [factories.GenreFactory(name=name) for name in names]
      }
    else:
      kwargs = {}
    # Create instance
    instance = factories.QuizRoomFactory(**kwargs)
    genre_name = instance.get_genres()

    assert expected == genre_name

  @pytest.mark.parametrize([
    'names',
    'expected',
  ], [
    ([], '-'),
    (['hoge-san'], 'hoge-san'),
    (['foo-san', 'bar-san'], 'bar-san,foo-san'),
  ], ids=[
    'is-empty',
    'only-one-creator',
    'many-creators',
  ])
  def test_check_get_creators_method(self, names, expected):
    if names:
      kwargs = {
        'creators': [factories.UserFactory(is_active=True, screen_name=name) for name in names]
      }
    else:
      kwargs = {}
    # Create instance
    instance = factories.QuizRoomFactory(**kwargs)
    creator_name = instance.get_creators()

    assert expected == creator_name

  @pytest.fixture(params=[
    'invalid-creators',
    'invalid-members',
  ])
  def get_invalid_member_info(self, request):
    key = request.param

    if key == 'invalid-creators':
      creators = [
        factories.UserFactory(is_active=True, role=RoleType.CREATOR),
        factories.UserFactory(is_active=True, role=RoleType.GUEST)
      ]
      members = [
        factories.UserFactory(is_active=True, role=RoleType.CREATOR),
        factories.UserFactory(is_active=True, role=RoleType.GUEST),
      ]
      instance = factories.QuizRoomFactory(creators=creators, members=members)
      err_msg = 'You have to assign only creators.'
    else:
      creators = factories.UserFactory.create_batch(2, is_active=True, role=RoleType.CREATOR)
      members = [
        factories.UserFactory(is_active=True, role=RoleType.CREATOR),
        factories.UserFactory(is_active=True, role=RoleType.GUEST),
        factories.UserFactory(is_active=True, role=RoleType.MANAGER),
      ]
      instance = factories.QuizRoomFactory(creators=creators, members=members)
      err_msg = 'You have to assign only players whose role is `Guest` or `Creator`.'

    yield instance, err_msg

  def test_invalid_clean_method(self, get_invalid_member_info):
    instance, err_msg = get_invalid_member_info

    with pytest.raises(ValidationError) as ex:
      instance.clean()

    assert err_msg in ex.value.args[0]

  def test_valid_clean_method(self):
    creators = list(factories.UserFactory.create_batch(2, is_active=True, role=RoleType.CREATOR))
    members = [
      factories.UserFactory(is_active=True, role=RoleType.CREATOR),
      factories.UserFactory(is_active=True, role=RoleType.GUEST),
    ]
    instance = factories.QuizRoomFactory(creators=creators, members=members)

    try:
      instance.clean()
    except Exception as ex:
      pytest.fail(f'Unexpected Error: {ex}')

# =========
# = Score =
# =========
@pytest.mark.quiz
@pytest.mark.model
@pytest.mark.django_db
class TestScore:
  def test_check_instance_type(self):
    room = factories.QuizRoomFactory(name='foo')
    score = factories.ScoreFactory.build(room=room, status=models.QuizStatusType.WAITING)
    str_val = 'foo(Waiting)'

    assert isinstance(score, models.Score)
    assert str(score) == str_val

  @pytest.mark.parametrize([
    'status',
    'expected',
  ], [
    (models.QuizStatusType.START, 'Start'),
    (models.QuizStatusType.WAITING, 'Waiting'),
    (models.QuizStatusType.SENT_QUESTION, 'Sent question'),
    (models.QuizStatusType.ANSWERING, 'Answering'),
    (models.QuizStatusType.RECEIVED_ANSWERS, 'Received answers'),
    (models.QuizStatusType.JUDGING, 'Judging'),
    (models.QuizStatusType.END, 'End'),
  ], ids=[
    'start',
    'waiting',
    'sent-question',
    'answering',
    'received-answers',
    'judging',
    'end',
  ])
  def test_check_label(self, status, expected):
    instance = factories.ScoreFactory(status=status)

    assert instance.get_status_label() == expected