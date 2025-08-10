import pytest
import tempfile
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from app_tests import factories
from quiz import validators
from quiz.models import Genre
from account.models import RoleType

UserModel = get_user_model()

@pytest.mark.quiz
@pytest.mark.validator
class TestCustomCSVFileValidator:
  compare_len = lambda _self, xs, ys: len(xs) == len(ys)
  compare_items = lambda _self, xs, ys: all([_x == _y for _x, _y in zip(xs, ys)])

  @pytest.mark.parametrize([
    'row',
    'records',
  ], [
    ([], [[]]),
    (['a'], [['a', 'b']]),
    (['a', 'b'], [['a', 'b'], ['c', 'd']]),
  ], ids=[
    'empty-pair',
    'one-item-in-each-array',
    'multi-items-in-each-array',
  ])
  def test_check_default_callback(self, row, records):
    validator = validators.CustomCSVFileValidator()
    is_valid_length = validator.length_checker(row)
    validator.record_checker(records)
    extracted = validator.extractor(row)

    assert is_valid_length
    assert self.compare_len(extracted, row)

  @pytest.mark.parametrize([
    'inputs',
    'outputs',
  ], [
    (['a', 'b', 'c'], ['a', 'b', 'c']),
    ([''], []),
    (['a', 'b', '', ''], ['a', 'b']),
  ], ids=[
    'valid-pattern',
    'empty-pattern',
    'multi-pattern',
  ])
  def test_check_internal_filter_method(self, inputs, outputs):
    validator = validators.CustomCSVFileValidator()
    estimated = validator._filter(inputs)

    assert self.compare_len(estimated, outputs)
    assert self.compare_items(estimated, outputs)

  @pytest.mark.parametrize([
    'has_header',
    'encoding',
  ], [
    (True, 'utf-8'), (False, 'utf-8'),
    (True, 'shift_jis'), (False, 'shift_jis'),
    (True, 'cp932'), (False, 'cp932'),
  ], ids=[
    'with-header-of-UTF8', 'without-header-of-UTF8',
    'with-header-of-SJIS', 'without-header-of-SJIS',
    'with-header-of-CP932', 'without-header-of-CP932',
  ])
  def test_valid_csvfile(self, has_header, encoding):
    validator = validators.CustomCSVFileValidator()

    with tempfile.NamedTemporaryFile(mode='r+', encoding=encoding, suffix='.csv') as tmp_fp:
      with open(tmp_fp.name, mode='rb+') as csv_file:
        if has_header:
          csv_file.write(b'Creator.pk,Genre,Question,Answer,IsCompleted\n')
        csv_file.writelines([
          b'a,b,c,d,True\n',
          b'creator-pk,genre-name,question,answer,False\n',
          b'c-pk1,g-name1,hoge,none,0\n',
        ])
        csv_file.seek(0)
        validator.validate(csv_file, encoding, header=has_header)

  @pytest.fixture(params=[
    'invalid-encoding',
    'failed-to-extract-data',
    'length-error',
    'data-error',
  ])
  def get_invalid_patterns(self, request):
    original = [
      b'uuid4-c-pk1,hoge-x,foo-y,bar-z,False\n',
      b'uuid4-c-pk2,foo-bar,one,two,True\n',
      b'uuid4-c-pk3,game,nothing,None,0\n',
      b'uuid4-c-pk4,cook,False,True,1\n',
    ]
    inputs = list(original)
    kwargs = {}
    encoding = 'utf-8'
    err_msg = ''

    if request.param == 'invalid-encoding':
      def inner(records):
        # encoding, object, start, end, reasons
        raise UnicodeDecodeError('cp932',b'',1,1,'')
      kwargs = {'record_checker': inner}
      encoding = 'cp932'
      err_msg = f'Failed to decode in line {len(original)} (Encoding: {encoding}).'
    elif request.param == 'failed-to-extract-data':
      def inner(row):
        raise TypeError('Failed to convert data')
      kwargs = {'extractor': inner}
      err_msg = 'Raise exception: Failed to convert data'
    elif request.param == 'length-error':
      inputs = list(original) + [b'7,hoge0,hoge1,hoge2,hoge3\n']
      kwargs = {'length_checker': lambda row: row[0] != '7'}
      err_msg = 'The length in line {} is invalid.'.format(len(inputs))
    elif request.param == 'data-error':
      def inner(*args, **kwargs):
        raise ValidationError('Invalid', code='invalid_file')
      kwargs = {'record_checker': inner}
      err_msg = 'Invalid'
    # Set data
    data = (inputs, kwargs, encoding, err_msg)

    return data

  def test_failed_to_validation(self, get_invalid_patterns):
    inputs, kwargs, encoding, err_msg = get_invalid_patterns
    # Create validator
    validator = validators.CustomCSVFileValidator(**kwargs)

    with tempfile.NamedTemporaryFile(mode='r+', encoding='utf-8', suffix='.csv') as tmp_fp:
      with open(tmp_fp.name, mode='rb+') as csv_file:
        csv_file.write(b'Creator.pk,Genre,Question,Answer,IsCompleted\n')
        csv_file.writelines(inputs)
        csv_file.seek(0)

        with pytest.raises(ValidationError) as ex:
          validator.validate(csv_file, encoding)
        collected_err = str(ex.value)

    assert err_msg in collected_err

  @pytest.mark.parametrize([
    'has_header',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'with-header',
    'without-header',
  ])
  def test_get_record_method(self, has_header):
    data = [
      b'uuid4-c-pk1,hoge-x,foo-y,bar-z,,False\n',
      b'uuid4-c-pk2,foo-bar,,one,two,True\n',
      b'uuid4-c-pk3,,game,nothing,None,0\n',
    ]
    expected = [
      ['uuid4-c-pk1', 'hoge-x', 'foo-y', 'bar-z', 'False'],
      ['uuid4-c-pk2', 'foo-bar', 'one', 'two', 'True'],
      ['uuid4-c-pk3', 'game', 'nothing', 'None', '0'],
    ]
    validator = validators.CustomCSVFileValidator()
    encoding = 'utf-8'

    with tempfile.NamedTemporaryFile(mode='r+', encoding=encoding, suffix='.csv') as tmp_fp:
      with open(tmp_fp.name, mode='rb+') as csv_file:
        if has_header:
          csv_file.write(b'Creator.pk,Genre,Question,Answer,IsCompleted\n')
        csv_file.writelines(data)
        csv_file.seek(0)
        validator.validate(csv_file, encoding, header=has_header)
      estimated = validator.get_record()

    assert self.compare_len(estimated, expected)
    assert all([self.compare_items(vals, exacts) for vals, exacts in zip(estimated, expected)])

@pytest.fixture(scope='module')
def get_specific_users(django_db_blocker):
  with django_db_blocker.unblock():
    users = [
      factories.UserFactory(is_active=True, email='test-validation0-c10@example.com', role=RoleType.CREATOR),
      factories.UserFactory(is_active=True, email='test-validation1-c11@example.com', role=RoleType.CREATOR),
      factories.UserFactory(is_active=True, email='test-validation2-c12@example.com', role=RoleType.CREATOR),
    ]
    users = UserModel.objects.filter(pk__in=[users[0].pk, users[1].pk, users[2].pk])

  return users

@pytest.mark.quiz
@pytest.mark.validator
@pytest.mark.django_db
class TestCustomCSVDataValidator:
  def test_check_default_queryset(self, get_specific_users):
    _ = get_specific_users
    validator = validators.CustomCSVDataValidator(UserModel, 'hoge')
    all_queryset = UserModel.objects.all()
    expected = [str(pk) for pk in validator.base_qs.values_list('pk', flat=True)]

    assert len(all_queryset) == len(expected)
    assert all([str(obj.pk) in expected for obj in all_queryset])

  @pytest.fixture(params=['genre', 'user-pk', 'user-email'])
  def get_validation_params(self, get_specific_users, get_genres, request):
    def inner(has_specific_data):
      users = get_specific_users
      genres = get_genres
      user = users[1]
      key = request.param

      if key == 'genre':
        qs = Genre.objects.filter(pk__in=[obj.pk for obj in genres])
        genre = genres[0]
        target_set = {genre.name,}
        condition = 'name__in'
        field_name = 'name'
        specific_data = {genre.name,} if has_specific_data else None
        use_uuid = False
      elif key == 'user-pk':
        qs = users
        target_set = {str(user.pk),}
        condition = 'pk__in'
        field_name = 'pk'
        specific_data = {str(user.pk),} if has_specific_data else None
        use_uuid = True
      else:
        qs = users
        target_set = {user.email,}
        condition = 'email__in'
        field_name = 'email'
        specific_data = {user.email,} if has_specific_data else None
        use_uuid = False

      return qs, target_set, condition, field_name, specific_data, use_uuid

    return inner

  @pytest.mark.parametrize([
    'has_specific_data',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'has-specific-data',
    'does-not-have-specific-data',
  ])
  def test_valid_validation(self, get_validation_params, has_specific_data):
    qs, target_set, condition, field_name, specific_data, use_uuid = get_validation_params(has_specific_data)
    validator = validators.CustomCSVDataValidator(UserModel, 'hoge', base_qs=qs)

    try:
      validator.validate(
        target_set,
        condition,
        field_name,
        specific_data=specific_data,
        use_uuid=use_uuid,
      )
    except Exception as ex:
      pytest.fail(f'Unexpected Error: {ex}')

  def test_invalid_uuid(self):
    validator = validators.CustomCSVDataValidator(UserModel, 'hoge')

    with pytest.raises(ValidationError) as ex:
      validator.validate({'invalid-c-pk',}, 'hoge', 'foo', use_uuid=True)

    assert 'The csv file includes invalid value(s).' in str(ex.value)

  def test_has_difference(self, get_specific_users):
    users = get_specific_users
    validator = validators.CustomCSVDataValidator(UserModel, 'hoge', base_qs=UserModel.objects.filter(pk__in=[users[0].pk]))
    targets = UserModel.objects.filter(pk__in=[users[1].pk, users[2].pk]).order_by('pk')
    values = ','.join([str(obj) for obj in targets])
    err_msg = f'The csv file includes invalid hoge(s). Details: {values}'

    with pytest.raises(ValidationError) as ex:
      validator.validate({str(users[1].pk), str(users[2].pk)}, 'pk__in', 'pk')

    assert err_msg in str(ex.value)