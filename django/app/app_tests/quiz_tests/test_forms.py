import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db.models import Q
from app_tests import factories, g_compare_options
from account.models import RoleType, IndividualGroup
from quiz import forms, models
import json

UserModel = get_user_model()

# ====================
# = Global functions =
# ====================
@pytest.mark.quiz
@pytest.mark.form
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
  estimated = forms.bool_converter(value)

  assert estimated == expected

# =============
# = GenreForm =
# =============
@pytest.mark.quiz
@pytest.mark.form
@pytest.mark.django_db
class TestGenreForm:
  @pytest.mark.parametrize([
    'params',
    'is_valid',
  ], [
    ({'name': 'hoge', 'is_enabled': True}, True),
    ({'name': 'hoge', 'is_enabled': False}, True),
    ({'name': 'hoge'}, False),
    ({'name': '1'*129}, False),
    ({}, False),
  ], ids=[
    'normal-input-with-enable-true-flag',
    'normal-input-without-enable-false-flag',
    'normal-input-without-enable-flag',
    'invalid-name-length',
    'empty-inputs',
  ])
  def test_validate_inputs(self, params, is_valid):
    form = forms.GenreForm(data=params)

    assert form.is_valid() == is_valid

@pytest.fixture
def get_each_types_of_genre(django_db_blocker, get_genres):
  with django_db_blocker.unblock():
    valid_genres = get_genres
    invalid_genre = factories.GenreFactory(is_enabled=False)

  return valid_genres, invalid_genre

# ==================
# = QuizSearchForm =
# ==================
@pytest.mark.quiz
@pytest.mark.form
@pytest.mark.django_db
class TestQuizSearchForm:
  pk_convertor = lambda _self, xs: [val.pk for val in xs]
  callback_user = lambda _self, item: f'{item.quizzes.all().filter(is_completed=True).count()},{item.code}'

  @pytest.mark.parametrize([
    'input_type',
    'has_manager_role',
  ], [
    ('genre', False),
    ('creator', True),
    ('creaotr', False),
  ], ids=lambda xs: str(xs))
  def test_invalid_patterns(self, input_type, has_manager_role):
    invalid_genre = factories.GenreFactory(is_enabled=False)
    creators = factories.UserFactory.create_batch(2, is_active=True, role=RoleType.CREATOR)
    user = creators[0] if not has_manager_role else factories.UserFactory(is_active=True, role=RoleType.MANAGER)

    if input_type == 'genre':
      params = {
        'genres': [invalid_genre.pk],
      }
    else:
      if has_manager_role:
        params = {
          'creators': [user.pk]
        }
      else:
        params = {
          'creators': [creators[1].pk],
        }
    form = forms.QuizSearchForm(user=user, data=params)

    assert not form.is_valid()

  @pytest.mark.parametrize([
    'data_type',
    'has_manager_role',
    'is_and_op',
  ], [
    ('only-genre', True, False),
    ('only-genre', False, False),
    ('only-creator', True, False),
    ('only-creator', False, False),
    ('both-data', True, False),
    ('both-data', False, False),
    ('both-data', True, True),
    ('both-data', False, True),
  ], ids=[
    'only-genre-by-manager',
    'only-genre-by-creator',
    'only-creator-by-manager',
    'only-creator-by-creator',
    'both-data-by-manager-with-or-op',
    'both-data-by-creator-with-or-op',
    'both-data-by-manager-with-and-op',
    'both-data-by-creator-with-and-op',
  ])
  def test_check_filtering(self, get_genres, data_type, has_manager_role, is_and_op):
    genres = get_genres[:4]
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).order_by('-pk')
    creators = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.CREATOR)
    creators = UserModel.objects.filter(pk__in=self.pk_convertor(creators)).order_by('-pk')
    user = creators[0] if not has_manager_role else factories.UserFactory(is_active=True, role=RoleType.MANAGER)
    instances = []

    for genre in genres:
      instances += [factories.QuizFactory(creator=creators[0], genre=genre, is_completed=False)]

      for creator in creators:
        instances += [factories.QuizFactory(creator=creator, genre=genre, is_completed=True)]
    all_quizzes = models.Quiz.objects.filter(pk__in=self.pk_convertor(instances))
    input_qs = all_quizzes if has_manager_role else all_quizzes.filter(creator=user)

    if data_type == 'only-genre':
      params = {
        'genres': [genres[2].pk, genres[3].pk],
        'is_and_op': False,
      }
      if has_manager_role:
        expected = input_qs.filter(genre__pk__in=params['genres'])
      else:
        expected = input_qs.filter(creator=user, genre__pk__in=params['genres'])
    elif data_type == 'only-creator':
      if has_manager_role:
        params = {
          'creators': [creators[0].pk, creators[1].pk],
          'is_and_op': False,
        }
        expected = input_qs.filter(creator__pk__in=params['creators'])
      else:
        params = {
          'creators': [user.pk],
          'is_and_op': False,
        }
        expected = input_qs.filter(creator=user)
    else:
      if has_manager_role:
        params = {
          'genres': [genres[2].pk, genres[3].pk],
          'creators': [creators[0].pk, creators[1].pk],
          'is_and_op': is_and_op,
        }
        if is_and_op:
          expected = input_qs.filter(genre__pk__in=params['genres'], creator__pk__in=params['creators'])
        else:
          expected = input_qs.filter(Q(genre__pk__in=params['genres']) | Q(creator__pk__in=params['creators']))
      else:
        params = {
          'genres': [genres[2].pk, genres[3].pk],
          'creators': [user.pk],
          'is_and_op': is_and_op,
        }
        if is_and_op:
          expected = input_qs.filter(genre__pk__in=params['genres'], creator__pk__in=params['creators'])
        else:
          expected = input_qs.filter(Q(genre__pk__in=params['genres']) | Q(creator__pk__in=params['creators']))
    # Create form instance
    form = forms.QuizSearchForm(user=user, data=params)
    is_valid = form.is_valid()
    queryset = form.filtering(input_qs)

    assert is_valid
    assert queryset.count() == expected.count()
    assert all([est.pk == exact.pk for est, exact in zip(queryset.order_by('pk'), expected.order_by('pk'))])

  def test_invalid_filtering_condition(self, get_genres):
    genres = get_genres[:4]
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).order_by('-pk')
    creators = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.CREATOR)
    creators = UserModel.objects.filter(pk__in=self.pk_convertor(creators)).order_by('-pk')
    user = factories.UserFactory(is_active=True, role=RoleType.MANAGER)
    all_quizzes = [factories.QuizFactory(creator=creators[0], genre=genre, is_completed=False) for genre in genres]
    all_quizzes = models.Quiz.objects.filter(pk__in=self.pk_convertor(all_quizzes))
    params = {}
    form = forms.QuizSearchForm(user=user, data=params)
    queryset = form.filtering(all_quizzes)

    assert queryset.count() == all_quizzes.count()
    assert all([est.pk == exact.pk for est, exact in zip(queryset.order_by('pk'), all_quizzes.order_by('pk'))])

  @pytest.mark.parametrize([
    'role',
  ], [
    (RoleType.CREATOR, ),
    (RoleType.MANAGER, ),
  ], ids=[
    'is-creator',
    'is-manager',
  ])
  def test_check_genre_options(self, mocker, get_genres, role):
    user = factories.UserFactory(is_active=True, role=role)
    creator = factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    genres = get_genres
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).order_by('-pk')
    # Create quiz
    for genre in genres:
      _ = factories.QuizFactory.create_batch(2, creator=creator, genre=genre)
    if user.is_creator():
      _ = factories.QuizFactory(creator=user, genre=genre)
    # Mock
    mocker.patch('quiz.models.GenreQuerySet.collect_active_genres', return_value=genres)
    form = forms.QuizSearchForm(user=user)
    str_options = form.get_genre_options
    options = json.loads(str_options)

    if user.has_manager_role():
      callback = lambda item: item.quizzes.all().count()
    else:
      callback = lambda item: item.quizzes.all().filter(creator=user).count()
    exacts = [
      {"text": f'{item}({callback(item)})', "value": str(item.pk), "selected": False} for item in genres
    ]

    assert isinstance(str_options, str)
    assert len(options) == len(exacts)
    assert g_compare_options(options, exacts)

  @pytest.mark.parametrize([
    'has_manager_role',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'by-manager',
    'by-creator',
  ])
  def test_check_creator_options(self, mocker, has_manager_role):
    creators = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.CREATOR)
    creators = UserModel.objects.filter(pk__in=self.pk_convertor(creators)).order_by('-pk')
    user = creators[0] if not has_manager_role else factories.UserFactory(is_active=True, role=RoleType.MANAGER)
    # Mock
    mocker.patch('account.models.CustomUserManager.collect_creators', return_value=creators)
    form = forms.QuizSearchForm(user=user)
    str_options = form.get_creator_options
    callback = lambda item: f'{item.quizzes.all().count()},{item.code}'
    options = json.loads(str_options)

    if has_manager_role:
      exacts = [
        {"text": f'{item}({callback(item)})', "value": str(item.pk), "selected": False} for item in creators
      ]
    else:
      selected_items = UserModel.objects.filter(pk__in=[user.pk])
      exacts = [
        {"text": f'{item}({callback(item)})', "value": str(item.pk), "selected": True} for item in selected_items
      ]

    assert isinstance(str_options, str)
    assert len(options) == len(exacts)
    assert g_compare_options(options, exacts)

# ============
# = QuizForm =
# ============
@pytest.mark.quiz
@pytest.mark.form
@pytest.mark.django_db
class TestQuizForm:
  @pytest.mark.parametrize([
    'input_type',
    'is_valid',
  ], [
    ('norma-inputs', True),
    ('without-completation', False),
    ('without-question-and-answer', True),
    ('without-genre', False),
    ('invalid-genre', False),
  ], ids=lambda xs: str(xs))
  def test_validate_inputs(self, get_each_types_of_genre, input_type, is_valid):
    user = factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    valid_genres, invalid_genre = get_each_types_of_genre
    # Define default param
    params = {
      'genre': str(valid_genres[0].pk),
      'question': 'hoge',
      'answer': 'foo',
      'is_completed': False,
    }
    err_msg = ''

    if input_type == 'without-completation':
      del params['is_completed']
      err_msg = 'This field is required.'
    elif input_type == 'without-question-and-answer':
      del params['question'], params['answer']
      params['is_completed'] = True
    elif input_type == 'without-genre':
      del params['genre']
      err_msg = 'This field is required.'
    elif input_type == 'invalid-genre':
      params['genre'] = str(invalid_genre.pk)
      err_msg = 'Select a valid choice. That choice is not one of the available choices.'
    # Create form instance
    form = forms.QuizForm(user=user, data=params)

    assert form.is_valid() == is_valid
    assert err_msg in str(form.errors)

  @pytest.mark.parametrize([
    'role',
    'is_valid',
    'err_msg',
  ], [
    (RoleType.MANAGER, True, ''),
    (RoleType.CREATOR, True, ''),
    (RoleType.GUEST, False, 'Need to be a creator role. Please check your role.'),
  ], ids=[
    'is-manager',
    'is-creator',
    'is-guest',
  ])
  def test_check_user_role(self, get_each_types_of_genre, role, is_valid, err_msg):
    user = factories.UserFactory(is_active=True, role=role)
    valid_genres, _ = get_each_types_of_genre
    params = {
      'genre': str(valid_genres[0].pk),
      'question': 'hoge',
      'answer': 'foo',
      'is_completed': True,
    }
    form = forms.QuizForm(user=user, data=params)

    assert form.is_valid() == is_valid
    assert err_msg in str(form.errors)

# ======================
# = QuizRoomSearchForm =
# ======================
@pytest.mark.quiz
@pytest.mark.form
@pytest.mark.django_db
class TestQuizRoomSearchForm:
  pk_convertor = lambda _self, xs: [val.pk for val in xs]

  @pytest.mark.parametrize([
    'name',
    'is_valid',
  ], [
    ('hoge-room', True),
    ('1'*129, False),
  ], ids=[
    'valid-pattern',
    'invalid-pattern',
  ])
  def test_check_validation(self, name, is_valid):
    params = {
      'name': name,
    }
    form = forms.QuizRoomSearchForm(data=params)

    assert form.is_valid() == is_valid

  @pytest.mark.parametrize([
    'name',
    'count',
  ], [
    ('hoge-room', 1),
    ('room', 2),
    ('no-room', 0),
  ], ids=[
    'only-one-room',
    'two-rooms',
    'no-rooms',
  ])
  def test_check_filtering(self, get_genres, name, count):
    user = factories.UserFactory(is_active=True, role=RoleType.GUEST)
    other = factories.UserFactory(is_active=True, role=RoleType.GUEST)
    genres = get_genres
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).order_by('-pk')
    rooms = [
      factories.QuizRoomFactory(owner=user, name='hoge-room', genres=genres, members=[]),
      factories.QuizRoomFactory(owner=other, name='foo-room', genres=genres, members=[user]),
    ]
    _ = factories.QuizRoomFactory(owner=user, name='not-relevant-instance', genres=genres, members=[])
    _ = factories.QuizRoomFactory(owner=other, name='ignore-instance', genres=genres, members=[user])
    input_qs = models.QuizRoom.objects.filter(pk__in=self.pk_convertor(rooms)).order_by('pk')
    params = {
      'name': name,
    }
    form = forms.QuizRoomSearchForm(data=params)
    is_valid = form.is_valid()
    queryset = form.filtering(input_qs)

    assert is_valid
    assert queryset.count() == count

  def test_invalid_filtering_condition(self, get_genres):
    user = factories.UserFactory(is_active=True, role=RoleType.GUEST)
    other = factories.UserFactory(is_active=True, role=RoleType.GUEST)
    genres = get_genres
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).order_by('-pk')
    rooms = [
      factories.QuizRoomFactory(owner=user, name='something', genres=genres, members=[]),
      factories.QuizRoomFactory(owner=other, name='anything', genres=genres, members=[user])
    ]
    input_qs = models.QuizRoom.objects.filter(pk__in=self.pk_convertor(rooms)).order_by('pk')
    params = {
      'name': '1'*129,
    }
    form = forms.QuizRoomSearchForm(data=params)
    queryset = form.filtering(input_qs).order_by('pk')

    assert queryset.count() == input_qs.count()
    assert all([val.pk == exact.pk for val, exact in zip(queryset, input_qs)])

# ================
# = QuizRoomForm =
# ================
@pytest.mark.quiz
@pytest.mark.form
@pytest.mark.django_db
class TestQuizRoomForm:
  pk_convertor = lambda _self, xs: [val.pk for val in xs]
  callback_user = lambda _self, item: f'{item.quizzes.all().count()},{item.code}'

  @pytest.mark.parametrize([
    'input_type',
    'is_valid',
  ], [
    # Valid patterns
    ('normal-type', True),
    ('genre-is-empty', True),
    ('creator-is-empty', True),
    ('member-is-empty', True),
    ('adds-user-except-friends', True),
    # Invalid patterns
    ('name-is-too-long', False),
    ('both-genres-and-creators-are-empty', False),
    ('max-question-is-empty', False),
    ('includes-invalid-genre', False),
    ('includes-invalid-creator', False),
    ('set-invalid-max-question', False),
  ], ids=lambda xs: str(xs).lower())
  def test_validate_inputs(self, mocker, get_each_types_of_genre, input_type, is_valid):
    _valid_genres, invalid_genre = get_each_types_of_genre
    valid_genre = _valid_genres[0]
    other_genre = _valid_genres[1]
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor([valid_genre, other_genre])).order_by('-pk')
    creators = factories.UserFactory.create_batch(2, is_active=True, role=RoleType.CREATOR)
    creators = UserModel.objects.filter(pk__in=self.pk_convertor(creators)).order_by('-pk')
    members = factories.UserFactory.create_batch(5, is_active=True, role=RoleType.GUEST)
    members = UserModel.objects.filter(pk__in=self.pk_convertor(members)).order_by('-pk')
    # Make quiz
    _ = factories.QuizFactory(creator=creators[0], genre=valid_genre, is_completed=True)
    _ = factories.QuizFactory(creator=creators[1], genre=valid_genre, is_completed=True)
    # Mock
    mocker.patch('quiz.models.GenreQuerySet.collect_valid_genres', return_value=genres)
    mocker.patch('account.models.CustomUserManager.collect_valid_creators', return_value=creators)
    mocker.patch('account.models.CustomUserManager.collect_valid_normal_users', return_value=members)
    # Define room owner
    owner = factories.UserFactory(is_active=True, role=RoleType.GUEST, friends=list(members))
    # Define default param
    params = {
      'name': 'hoge',
      'genres': genres,
      'creators': creators,
      'members': members,
      'max_question': 1,
      'is_enabled': False,
    }
    err_msg = ''
    # Valid patterns
    if input_type == 'genre-is-empty':
      del params['genres']
    elif input_type == 'creator-is-empty':
      del params['creators']
    elif input_type == 'member-is-empty':
      del params['members']
    elif input_type == 'adds-user-except-friends':
      other = factories.UserFactory(is_active=True)
      new_member = UserModel.objects.filter(pk__in=self.pk_convertor(list(members) + [other])).order_by('-pk')
      params['members'] = new_member
      mocker.patch('account.models.CustomUserManager.collect_valid_normal_users', return_value=new_member)
    # Inalid patterns
    elif input_type == 'name-is-too-long':
      params['name'] = '1'*129
      err_msg = 'Ensure this value has at most 128 characters'
    elif input_type == 'both-genres-and-creators-are-empty':
      del params['genres']
      del params['creators']
      err_msg = 'You have to assign at least one of genres and creators to the quiz room.'
    elif input_type == 'max-question-is-empty':
      del params['max_question']
      err_msg = 'This field is required.'
    elif input_type == 'includes-invalid-genre':
      params['genres'] = models.Genre.objects.filter(pk__in=self.pk_convertor(list(genres) + [invalid_genre])).order_by('-pk')
      err_msg = f'Select a valid choice. {invalid_genre.pk} is not one of the available choices.'
    elif input_type == 'includes-invalid-creator':
      other = factories.UserFactory(is_active=True, role=RoleType.GUEST)
      params['creators'] = UserModel.objects.filter(pk__in=self.pk_convertor(list(creators) + [other])).order_by('-pk')
      err_msg = f'Select a valid choice. {other.pk} is not one of the available choices.'
    elif input_type == 'set-invalid-max-question':
      params['max_question'] = 256
      err_msg = 'The number of quizzes this system can set is 2, but the requested value is {}. Please check the condition.'.format(params['max_question'])

    # Define form instance
    form = forms.QuizRoomForm(user=owner, data=params)

    assert form.is_valid() == is_valid
    assert err_msg in str(form.errors)

  @pytest.fixture(params=['none', 'default'])
  def get_instance_type(self, request):
    yield request.param

  def test_check_genre_options(self, mocker, get_genres, get_instance_type):
    instance_type = get_instance_type
    owner = factories.UserFactory(is_active=True)
    genres = get_genres
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).order_by('-pk')
    # Mock
    mocker.patch('quiz.models.GenreQuerySet.collect_valid_genres', return_value=genres)
    # Set params
    if instance_type == 'none':
      params = {}
    else:
      params = {
        'name': 'hoge',
        'genres': [genres[1].pk],
        'is_enabled': True,
      }
    form = forms.QuizRoomForm(user=owner, data=params)
    if instance_type == 'none':
      form.instance = None
    str_options = form.get_genre_options
    options = json.loads(str_options)
    callback = lambda item: item.quizzes.all().filter(is_completed=True).count()
    if form.instance is not None:
      selected_items = form.instance.genres.all()
      rest_items = genres.exclude(pk__in=self.pk_convertor(selected_items))
      exacts = [
        {"text": f'{item}({callback(item)})', "value": str(item.pk), "selected": False} for item in rest_items
      ] + [
        {"text": f'{item}({callback(item)})', "value": str(item.pk), "selected": True} for item in selected_items
      ]
    else:
      exacts = [
        {"text": f'{item}({callback(item)})', "value": str(item.pk), "selected": False} for item in genres
      ]

    assert isinstance(str_options, str)
    assert len(options) == len(exacts)
    assert g_compare_options(options, exacts)

  def test_check_creator_options(self, mocker, get_instance_type):
    instance_type = get_instance_type
    owner = factories.UserFactory(is_active=True)
    creators = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.CREATOR)
    creators = UserModel.objects.filter(pk__in=self.pk_convertor(creators)).order_by('-pk')
    # Mock
    mocker.patch('account.models.CustomUserManager.collect_valid_creators', return_value=creators)
    # Set params
    if instance_type == 'none':
      params = {}
    else:
      params = {
        'name': 'hoge',
        'creators': [creators[1].pk],
        'is_enabled': True,
      }
    form = forms.QuizRoomForm(user=owner, data=params)
    if instance_type == 'none':
      form.instance = None
    str_options = form.get_creator_options
    options = json.loads(str_options)
    if form.instance is not None:
      selected_items = form.instance.creators.all()
      rest_items = creators.exclude(pk__in=self.pk_convertor(selected_items))
      exacts = [
        {"text": f'{item}({self.callback_user(item)})', "value": str(item.pk), "selected": False} for item in rest_items
      ] + [
        {"text": f'{item}({self.callback_user(item)})', "value": str(item.pk), "selected": True} for item in selected_items
      ]
    else:
      exacts = [
        {"text": f'{item}({self.callback_user(item)})', "value": str(item.pk), "selected": False} for item in creators
      ]

    assert isinstance(str_options, str)
    assert len(options) == len(exacts)
    assert g_compare_options(options, exacts)

  def test_check_member_options(self, mocker, get_genres, get_instance_type):
    instance_type = get_instance_type
    owner = factories.UserFactory(is_active=True)
    genre = get_genres[0]
    members = factories.UserFactory.create_batch(3, is_active=True)
    members = UserModel.objects.filter(pk__in=self.pk_convertor(members)).order_by('-pk')
    # Mock
    mocker.patch('account.models.CustomUserManager.collect_valid_normal_users', return_value=members)
    # Set params
    if instance_type == 'none':
      params = {}
    else:
      params = {
        'name': 'hoge',
        'genres': [genre.pk],
        'members': [members[1].pk],
        'is_enabled': True,
      }
    form = forms.QuizRoomForm(user=owner, data=params)
    if instance_type == 'none':
      form.instance = None
    str_options = form.get_member_options
    options = json.loads(str_options)
    if form.instance is not None:
      selected_items = form.instance.members.all()
      rest_items = members.exclude(pk__in=self.pk_convertor(selected_items))
      exacts = [
        {"text": f'{item}({item.code})', "value": str(item.pk), "selected": False} for item in rest_items
      ] + [
        {"text": f'{item}({item.code})', "value": str(item.pk), "selected": True} for item in selected_items
      ]
    else:
      exacts = [
        {"text": f'{item}({item.code})', "value": str(item.pk), "selected": False} for item in (members)
      ]

    assert isinstance(str_options, str)
    assert len(options) == len(exacts)
    assert g_compare_options(options, exacts)

  def test_check_postprocess(self, mocker, get_genres):
    owner = factories.UserFactory(is_active=True)
    one_genre = get_genres[0]
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor([one_genre])).order_by('-pk')
    creators = factories.UserFactory.create_batch(2, is_active=True, role=RoleType.CREATOR)
    creators = UserModel.objects.filter(pk__in=self.pk_convertor(creators)).order_by('-pk')
    members = factories.UserFactory.create_batch(5, is_active=True, role=RoleType.GUEST)
    members = UserModel.objects.filter(pk__in=self.pk_convertor(members)).order_by('-pk')
    # Make quiz
    _ = factories.QuizFactory(creator=creators[1], genre=one_genre, is_completed=True)
    # Mock
    mocker.patch('quiz.models.GenreQuerySet.collect_valid_genres', return_value=genres)
    mocker.patch('account.models.CustomUserManager.collect_valid_creators', return_value=creators)
    mocker.patch('account.models.CustomUserManager.collect_valid_normal_users', return_value=members)

    if len(members) > 5:
      members = members[:5]
    params = {
      'name': 'hoge',
      'genres': genres,
      'creators': creators,
      'members': members,
      'max_question': 1,
      'is_enabled': False,
    }
    form = forms.QuizRoomForm(user=owner, data=params)
    is_valid = form.is_valid()
    instance = form.save()

    try:
      models.QuizRoom.objects.get(pk=instance.pk)
    except Exception as ex:
      pytest.fail(f'Unexpected Error: {ex}')
    ids_genre = self.pk_convertor(genres)
    ids_creator = self.pk_convertor(creators)
    ids_member = self.pk_convertor(members)

    assert is_valid
    assert all([val.pk in ids_genre for val in instance.genres.all()])
    assert all([val.pk in ids_creator for val in instance.creators.all()])
    assert all([val.pk in ids_member for val in instance.members.all()])