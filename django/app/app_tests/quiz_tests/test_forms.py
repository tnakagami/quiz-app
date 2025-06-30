import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
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
def get_genres(django_db_blocker):
  with django_db_blocker.unblock():
    valid_genre = factories.GenreFactory(is_enabled=True)
    invalid_genre = factories.GenreFactory(is_enabled=False)

  return valid_genre, invalid_genre

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
  def test_validate_inputs(self, get_genres, input_type, is_valid):
    user = factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    valid_genre, invalid_genre = get_genres
    # Define default param
    params = {
      'genre': str(valid_genre.pk),
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
  def test_check_user_role(self, get_genres, role, is_valid, err_msg):
    user = factories.UserFactory(is_active=True, role=role)
    valid_genre, _ = get_genres
    params = {
      'genre': str(valid_genre.pk),
      'question': 'hoge',
      'answer': 'foo',
      'is_completed': True,
    }
    form = forms.QuizForm(user=user, data=params)

    assert form.is_valid() == is_valid
    assert err_msg in str(form.errors)

# ================
# = QuizRoomForm =
# ================
@pytest.mark.quiz
@pytest.mark.form
@pytest.mark.django_db
class TestQuizRoomForm:
  pk_convertor = lambda _self, xs: [val.pk for val in xs]

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
  ], ids=lambda xs: str(xs).lower())
  def test_validate_inputs(self, mocker, get_genres, input_type, is_valid):
    valid_genre, invalid_genre = get_genres
    other_genre = factories.GenreFactory(is_enabled=True)
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor([valid_genre, other_genre])).order_by('-pk')
    creators = factories.UserFactory.create_batch(2, is_active=True, role=RoleType.CREATOR)
    creators = UserModel.objects.filter(pk__in=self.pk_convertor(creators)).order_by('-pk')
    members = factories.UserFactory.create_batch(5, is_active=True, role=RoleType.GUEST)
    members = UserModel.objects.filter(pk__in=self.pk_convertor(members)).order_by('-pk')
    # Mock
    mocker.patch('quiz.models.GenreQuerySet.collect_active_genres', return_value=genres)
    mocker.patch('account.models.CustomUserManager.collect_creators', return_value=creators)
    mocker.patch('account.models.CustomUserManager.collect_valid_normal_users', return_value=members)
    # Define room owner
    owner = factories.UserFactory(is_active=True, role=RoleType.GUEST, friends=list(members))
    # Define default param
    params = {
      'name': 'hoge',
      'genres': genres,
      'creators': creators,
      'members': members,
      'max_question': 10,
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

    # Define form instance
    form = forms.QuizRoomForm(user=owner, data=params)
    print(form.errors)

    assert form.is_valid() == is_valid
    assert err_msg in str(form.errors)

  @pytest.fixture(params=['none', 'default'])
  def get_instance_type(self, request):
    yield request.param

  def test_check_genre_options(self, mocker, get_instance_type):
    instance_type = get_instance_type
    owner = factories.UserFactory(is_active=True)
    genres = factories.GenreFactory.create_batch(3, is_enabled=True)
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).order_by('-pk')
    # Mock
    mocker.patch('quiz.models.GenreQuerySet.collect_active_genres', return_value=genres)
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
    if form.instance is not None:
      selected_items = form.instance.genres.all()
      rest_items = genres.exclude(pk__in=self.pk_convertor(selected_items))
      exacts = [
        {"text": str(item), "value": str(item.pk), "selected": False} for item in rest_items
      ] + [
        {"text": str(item), "value": str(item.pk), "selected": True} for item in selected_items
      ]
    else:
      exacts = [
        {"text": str(item), "value": str(item.pk), "selected": False} for item in genres
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
    mocker.patch('account.models.CustomUserManager.collect_creators', return_value=creators)
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
        {"text": f'{item}({item.code})', "value": str(item.pk), "selected": False} for item in rest_items
      ] + [
        {"text": f'{item}({item.code})', "value": str(item.pk), "selected": True} for item in selected_items
      ]
    else:
      exacts = [
        {"text": f'{item}({item.code})', "value": str(item.pk), "selected": False} for item in creators
      ]

    assert isinstance(str_options, str)
    assert len(options) == len(exacts)
    assert g_compare_options(options, exacts)

  def test_check_member_options(self, mocker, get_instance_type):
    instance_type = get_instance_type
    owner = factories.UserFactory(is_active=True)
    genre = factories.GenreFactory(is_enabled=True)
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

  def test_check_postprocess(self, mocker):
    owner = factories.UserFactory(is_active=True)
    one_genre = factories.GenreFactory(is_enabled=True)
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor([one_genre])).order_by('-pk')
    creators = factories.UserFactory.create_batch(2, is_active=True, role=RoleType.CREATOR)
    creators = UserModel.objects.filter(pk__in=self.pk_convertor(creators)).order_by('-pk')
    members = factories.UserFactory.create_batch(5, is_active=True, role=RoleType.GUEST)
    members = UserModel.objects.filter(pk__in=self.pk_convertor(members)).order_by('-pk')
    # Mock
    mocker.patch('quiz.models.GenreQuerySet.collect_active_genres', return_value=genres)
    mocker.patch('account.models.CustomUserManager.collect_creators', return_value=creators)
    mocker.patch('account.models.CustomUserManager.collect_valid_normal_users', return_value=members)

    if len(members) > 5:
      members = members[:5]
    params = {
      'name': 'hoge',
      'genres': genres,
      'creators': creators,
      'members': members,
      'max_question': 10,
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