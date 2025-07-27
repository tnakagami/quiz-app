import pytest
from django.core.exceptions import ValidationError, NON_FIELD_ERRORS
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db.utils import IntegrityError
from app_tests import factories, g_compare_options
from account.models import RoleType, IndividualGroup
from quiz import forms, models
from datetime import datetime, timezone
import json
import tempfile

UserModel = get_user_model()

# ====================
# = Global functions =
# ====================
@pytest.mark.quiz
@pytest.mark.form
def test_generate_default_filename(mocker):
  mocker.patch(
    'quiz.forms.get_current_time',
    return_value=datetime(2021,7,3,11,7,48,microsecond=123456,tzinfo=timezone.utc),
  )
  expected = '20210703-200748'
  filename = forms.generate_default_filename()

  assert filename == expected

class DummyFile:
  def __init__(self, val):
    self.size = val

class DummySettings:
  def __init__(self, val):
    self.MAX_CSV_FILESIZE = val

@pytest.fixture
def mock_csv_filesize(mocker):
  mocker.patch('quiz.forms.settings', new=DummySettings(3 * 1024 * 1024))

  return mocker

@pytest.mark.quiz
@pytest.mark.form
@pytest.mark.parametrize([
  'input_value',
], [
  (0, ),
  (1, ),
  (3 * 1024 * 1024, ),
], ids=[
  'is-zero',
  'is-one',
  'maximum-value',
])
def test_valid_check_filesize_function(mock_csv_filesize, input_value):
  _ = mock_csv_filesize
  instance = DummyFile(input_value)

  try:
    _ = forms.check_filesize(instance)
  except ValidationError as ex:
    pytest.fail(f'Unexpected Error: {ex}')

@pytest.mark.quiz
@pytest.mark.form
def test_invalid_check_filesize_function(mock_csv_filesize):
  _ = mock_csv_filesize
  instance = DummyFile(3 * 1024 * 1024 + 1)
  err_msg = 'Input filesize is too large. Max filesize: 3 MB'

  with pytest.raises(ValidationError) as ex:
    forms.check_filesize(instance)

  assert err_msg in str(ex.value)

class Common:
  pk_convertor = lambda _self, xs: [val.pk for val in xs]

  @pytest.fixture(params=['is-creator', 'is-manager'], scope='module')
  def get_quiz_accounts(self, request, django_db_blocker):
    config = {
      'is-creator': {'is_active': True, 'role': RoleType.CREATOR},
      'is-manager': {'is_active': True, 'role': RoleType.MANAGER},
    }
    key = request.param
    # Create account
    with django_db_blocker.unblock():
      kwargs = config[key]
      user = factories.UserFactory(**kwargs)

    return user

# =============
# = GenreForm =
# =============
@pytest.mark.quiz
@pytest.mark.form
@pytest.mark.django_db
class TestGenreForm(Common):
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

# =====================
# = GenreDownloadForm =
# =====================
@pytest.mark.quiz
@pytest.mark.form
@pytest.mark.django_db
class TestGenreDownloadForm(Common):
  @pytest.fixture
  def set_custom_mock(self, mocker):
    mocker.patch(
      'quiz.forms.get_current_time',
      return_value=datetime(2022,7,3,10,58,3,microsecond=123456,tzinfo=timezone.utc),
    )
    mocker.patch('quiz.models.Genre.get_response_kwargs',
      side_effect=lambda name: {'filename': f'genre-{name}.csv'},
    )

    return mocker

  @pytest.mark.parametrize([
    'name',
    'expected',
  ], [
    ('hoge', 'genre-hoge.csv'),
    ('foo.csv', 'genre-foo.csv'),
    ('foo.txt', 'genre-foo.txt.csv'),
    ('.csv', 'genre-20220703-195803.csv'),
  ], ids=[
    'norma-pattern',
    'with-extention',
    'with-other-extention',
    'only-extension',
  ])
  def test_valid_get_response_kwargs(self, set_custom_mock, name, expected):
    _ = set_custom_mock
    params = {
      'filename': name,
    }
    form = forms.GenreDownloadForm(data=params)
    is_valid = form.is_valid()
    kwargs = form.create_response_kwargs()

    assert is_valid
    assert kwargs['filename'] == expected

  def test_invalid_params(self, set_custom_mock):
    _ = set_custom_mock
    params = {
      'filename': '1'*129,
    }
    form = forms.GenreDownloadForm(data=params)
    is_valid = form.is_valid()

    assert not is_valid

# ==================
# = QuizSearchForm =
# ==================
@pytest.mark.quiz
@pytest.mark.form
@pytest.mark.django_db
class TestQuizSearchForm(Common):
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

# ==================
# = QuizUploadForm =
# ==================
@pytest.mark.quiz
@pytest.mark.form
@pytest.mark.django_db
class TestQuizUploadForm(Common):
  @pytest.fixture
  def get_form_params_with_fds(self):
    def inner(encoding, suffix='.csv'):
      # Setup temporary file
      tmp_fp = tempfile.NamedTemporaryFile(mode='r+', encoding=encoding, suffix=suffix)
      with open(tmp_fp.name, encoding=encoding, mode='w') as csv_file:
        csv_file.writelines(['Creator.pk,Genre,Question,Answer,IsCompleted\n', 'a,b,c,d,True\n', 'a,b,c,d,False\n'])
        csv_file.flush()
      with open(tmp_fp.name, encoding=encoding, mode='r') as fin:
        csv_file = SimpleUploadedFile(fin.name, bytes(fin.read(), encoding=fin.encoding))
        # Create form data
        params = {
          'encoding': encoding,
          'header': True,
        }
        files = {
          'csv_file': csv_file,
        }

      return tmp_fp, csv_file, params, files

    return inner

  @pytest.fixture(params=['utf-8-encoding', 'sjis-encoding', 'cp932-encoding'])
  def get_valid_form_param(self, request, get_form_params_with_fds):
    encoding = 'utf-8'
    # Define encoding
    if request.param == 'utf-8-encoding':
      encoding = 'utf-8'
    elif request.param == 'sjis-encoding':
      encoding = 'shift_jis'
    elif request.param == 'cp932-encoding':
      encoding = 'cp932'
    # Setup temporary file
    tmp_fp, csv_file, params, files = get_form_params_with_fds(encoding)

    yield params, files

    # Post-process
    csv_file.close()
    tmp_fp.close()

  def test_valid_input_pattern(self, mocker, get_quiz_accounts, get_valid_form_param):
    user = get_quiz_accounts
    params, files = get_valid_form_param
    form = forms.QuizUploadForm(user=user, data=params, files=files)
    mocker.patch.object(form.validator, 'validate', return_value=None)
    is_valid = form.is_valid()

    assert is_valid

  @pytest.fixture(params=['without-encoding', 'without-csvfile', 'without-header'])
  def get_invalid_form_param(self, request, get_form_params_with_fds):
    # Setup temporary file
    tmp_fp, csv_file, params, files = get_form_params_with_fds('utf-8')
    err_msg = 'This field is required'
    # Setup form data
    if request.param == 'without-encoding':
      del params['encoding']
    elif request.param == 'without-csvfile':
      del files['csv_file']
    elif request.param == 'without-header':
      del params['header']

    yield params, files, err_msg

    # Post-process
    csv_file.close()
    tmp_fp.close()

  def test_invalid_field_data(self, mocker, get_quiz_accounts, get_invalid_form_param):
    user = get_quiz_accounts
    params, files, err_msg = get_invalid_form_param
    form = forms.QuizUploadForm(user=user, data=params, files=files)
    mocker.patch.object(form.validator, 'validate', return_value=None)
    is_valid = form.is_valid()

    assert not is_valid
    assert err_msg in str(form.errors)

  @pytest.fixture
  def get_params_for_register_method(self, get_form_params_with_fds):
    tmp_fp, csv_file, params, files = get_form_params_with_fds('utf-8')

    yield params, files

    # Post-process
    csv_file.close()
    tmp_fp.close()

  def test_check_register_quizzes(self, mocker, get_genres, get_quiz_accounts, get_params_for_register_method):
    genres = get_genres
    user = get_quiz_accounts
    creator = user if user.is_creator() else factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    records = [
      [str(creator.pk), genres[0].name, 'quiz-hogehoge', 'foofoo', True],
      [str(creator.pk), genres[1].name, 'quiz-text1', 'ans1', False],
      [str(creator.pk), genres[1].name, 'quiz-text2', 'ans2', True],
      [str(creator.pk), genres[2].name, 'quiz-bar', 'nugar', False],
    ]
    # Create form
    params, files = get_params_for_register_method
    form = forms.QuizUploadForm(user=user, data=params, files=files)
    mocker.patch.object(form.validator, 'validate', return_value=None)
    mocker.patch.object(form.validator, 'get_record', return_value=records)
    is_valid = form.is_valid()
    instances = form.register_quizzes()
    counts = models.Quiz.objects.filter(pk__in=self.pk_convertor(instances)).count()

    assert is_valid
    assert not form.has_error(NON_FIELD_ERRORS)
    assert counts == len(records)

  def test_raise_exception_in_bulk_create(self, get_genres, mocker, get_quiz_accounts, get_params_for_register_method):
    genre = get_genres[0]
    user = get_quiz_accounts
    creator = user if user.is_creator() else factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    err_msg = 'Include invalid records. Please check the detail:'
    # Create form
    params, files = get_params_for_register_method
    form = forms.QuizUploadForm(user=user, data=params, files=files)
    mocker.patch.object(form.validator, 'validate', return_value=None)
    mocker.patch.object(form.validator, 'get_record', return_value=[[1], [2], [3]])
    mocker.patch('quiz.models.Quiz.get_instance_from_list', side_effect=lambda row: factories.QuizFactory.build(creator=creator, genre=genre))
    mocker.patch('quiz.models.Quiz.objects.bulk_create', side_effect=IntegrityError('Invalid data'))
    is_valid = form.is_valid()
    instances = form.register_quizzes()

    assert is_valid
    assert form.has_error(NON_FIELD_ERRORS)
    assert err_msg in str(form.non_field_errors())
    assert len(instances) == 0

@pytest.mark.quiz
@pytest.mark.form
@pytest.mark.parametrize([
  'data',
], [
  ('abc', ),
  (123, ),
  (3.14, ),
  ([3, 'a'], ),
  ((3, '1', 4), ),
  ({'hoge': 'bar', 'k': 3}, ),
  (True, ),
  (None, ),
], ids=[
  'is-string',
  'is-int',
  'is-float',
  'is-list',
  'is-tuple',
  'is-dict',
  'is-bool',
  'is-none',
])
def test_custom_multiple_choicefield(data):
  field = forms.CustomMultipleChoiceField(
    label='',
    choices=[],
    required=False,
  )

  assert field.valid_value(data)

# ====================
# = QuizDownloadForm =
# ====================
@pytest.mark.quiz
@pytest.mark.form
@pytest.mark.django_db
class TestQuizDownloadForm(Common):
  @pytest.fixture
  def set_custom_mock(self, mocker):
    mocker.patch(
      'quiz.forms.get_current_time',
      return_value=datetime(2022,7,3,11,58,3,microsecond=123456,tzinfo=timezone.utc),
    )
    mocker.patch('quiz.models.Genre.get_response_kwargs',
      side_effect=lambda name: {'filename': f'genre-{name}.csv'},
    )

    return mocker

  @pytest.mark.parametrize([
    'name',
    'expected',
  ], [
    ('hoge', 'quiz-hoge.csv'),
    ('foo.csv', 'quiz-foo.csv'),
    ('foo.txt', 'quiz-foo.txt.csv'),
    ('.csv', 'quiz-20220703-205803.csv'),
  ], ids=[
    'norma-pattern',
    'with-extention',
    'with-other-extention',
    'only-extension',
  ])
  def test_valid_get_response_kwargs(self, set_custom_mock, get_quiz_accounts, name, expected):
    _ = set_custom_mock
    user = get_quiz_accounts
    params = {
      'filename': name,
    }
    form = forms.QuizDownloadForm(user=user, data=params)
    is_valid = form.is_valid()
    kwargs = form.create_response_kwargs()

    assert is_valid
    assert kwargs['filename'] == expected

  def test_invalid_params(self, set_custom_mock, get_quiz_accounts):
    _ = set_custom_mock
    user = get_quiz_accounts
    params = {
      'filename': '1'*129,
    }
    form = forms.QuizDownloadForm(user=user, data=params)
    is_valid = form.is_valid()

    assert not is_valid

  def test_check_clean_quizzes_method(self, get_genres, get_quiz_accounts):
    user = get_quiz_accounts
    genre = get_genres[0]
    creators = factories.UserFactory.create_batch(2, is_active=True, role=RoleType.CREATOR)
    instances = [factories.QuizFactory(creator=creator, genre=genre) for creator in creators]
    # Set expected value
    if user.has_manager_role():
      expected = self.pk_convertor(instances)
    else:
      own = factories.QuizFactory(creator=user, genre=genre)
      instances += [own]
      expected = [own.pk]
    # Create form instance
    form = forms.QuizDownloadForm(user=user)
    form.cleaned_data = {'quizzes': self.pk_convertor(instances)}
    outputs = form.clean_quizzes()

    assert len(outputs) == len(expected)
    assert all([pk in expected for pk in outputs])

# ============
# = QuizForm =
# ============
@pytest.mark.quiz
@pytest.mark.form
@pytest.mark.django_db
class TestQuizForm(Common):
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
class TestQuizRoomSearchForm(Common):
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
class TestQuizRoomForm(Common):
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
      err_msg = 'You have to assign at least one of genres or creators to the quiz room.'
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
    assert hasattr(instance, 'score')
    assert isinstance(instance.score, models.Score)
    assert instance.score.index == 1
    assert instance.score.status == models.QuizStatusType.START
    assert isinstance(instance.score.sequence, dict)
    assert isinstance(instance.score.detail, dict)
    assert all([val.pk in ids_genre for val in instance.genres.all()])
    assert all([val.pk in ids_creator for val in instance.creators.all()])
    assert all([val.pk in ids_member for val in instance.members.all()])

  def test_check_call_reset_method_in_postprocess(self, mocker, get_genres):
    owner = factories.UserFactory(is_active=True)
    genres = get_genres[:4]
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).order_by('-pk')
    creators = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.CREATOR)
    creators = UserModel.objects.filter(pk__in=self.pk_convertor(creators)).order_by('-pk')
    members = factories.UserFactory.create_batch(5, is_active=True, role=RoleType.GUEST)
    members = UserModel.objects.filter(pk__in=self.pk_convertor(members)).order_by('-pk')
    # Make quiz
    quizzes = [
      factories.QuizFactory(creator=creators[0], genre=genres[0], is_completed=True),  # 0
      factories.QuizFactory(creator=creators[0], genre=genres[1], is_completed=True),  # 1
      factories.QuizFactory(creator=creators[0], genre=genres[2], is_completed=True),  # 2
      factories.QuizFactory(creator=creators[1], genre=genres[0], is_completed=True),  # 3, Is not selected
      factories.QuizFactory(creator=creators[1], genre=genres[1], is_completed=False), # 4, Is not selected
      factories.QuizFactory(creator=creators[1], genre=genres[2], is_completed=True),  # 5
      factories.QuizFactory(creator=creators[2], genre=genres[3], is_completed=False), # 6, Is not selected
      factories.QuizFactory(creator=creators[2], genre=genres[1], is_completed=True),  # 7
      factories.QuizFactory(creator=creators[2], genre=genres[2], is_completed=True),  # 8
    ]
    exacts = [quizzes[idx] for idx in [0, 1, 2, 5, 7, 8]]
    # Create parameter
    params = {
      'name': 'hoge',
      'genres': [genres[1], genres[2]],
      'creators': [creators[0], creators[2]],
      'members': members,
      'max_question': 6,
      'is_enabled': True,
    }
    # Mock
    quizzes = models.Quiz.objects.filter(pk__in=self.pk_convertor(quizzes))
    def _mock_filter(*args, **kwargs):
      if kwargs.get('is_completed', False):
        ret = quizzes.filter(is_completed=True)
      else:
        ret = quizzes.filter(is_completed=True).filter(*args, **kwargs)
      return ret
    mocker.patch('quiz.models.Quiz.objects.filter', side_effect=_mock_filter)
    mocker.patch('quiz.models.GenreQuerySet.collect_valid_genres', return_value=genres)
    mocker.patch('account.models.CustomUserManager.collect_valid_creators', return_value=creators)
    mocker.patch('account.models.CustomUserManager.collect_valid_normal_users', return_value=members)
    # Create form
    form = forms.QuizRoomForm(user=owner, data=params)
    is_valid = form.is_valid()
    instance = form.save()

    try:
      models.QuizRoom.objects.get(pk=instance.pk)
    except Exception as ex:
      pytest.fail(f'Unexpected Error: {ex}')
    sequence_ids = [str(item.pk) for item in exacts]
    detail_ids = [str(owner.pk)] + [str(pk) for pk in members.values_list('pk', flat=True)]

    assert is_valid
    assert instance.score.index == 1
    assert instance.score.status == models.QuizStatusType.START
    assert all([pk in sequence_ids for pk in list(instance.score.sequence.values())])
    assert all([pk in detail_ids for pk in list(instance.score.detail.keys())])