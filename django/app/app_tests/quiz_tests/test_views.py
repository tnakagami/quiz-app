import pytest
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.urls import reverse
from app_tests import (
  status,
  factories,
  g_generate_item,
  g_compare_options,
)
from account.models import RoleType
from quiz import views, models
import uuid

UserModel = get_user_model()

class Common:
  @pytest.fixture(scope='module', params=['superuser', 'manager', 'creator', 'guest'])
  def get_user(self, django_db_blocker, request):
    patterns = {
      'superuser': {'is_active': True, 'is_staff': True, 'is_superuser': True, 'role': RoleType.GUEST},
      'manager': {'is_active': True, 'role': RoleType.MANAGER},
      'creator': {'is_active': True, 'role': RoleType.CREATOR},
      'guest': {'is_active': True, 'role': RoleType.GUEST},
    }
    key = request.param
    kwargs = patterns[key]
    # Get user instance
    with django_db_blocker.unblock():
      user = factories.UserFactory(**kwargs)

    return key, user

  @pytest.fixture(scope='module')
  def get_manager(self, django_db_blocker):
    with django_db_blocker.unblock():
      manager = factories.UserFactory(is_active=True, role=RoleType.MANAGER)

    return manager

  @pytest.fixture(scope='module')
  def get_creator(self, django_db_blocker):
    with django_db_blocker.unblock():
      creator = factories.UserFactory(is_active=True, role=RoleType.CREATOR)

    return creator

  @pytest.fixture(scope='module')
  def get_guest(self, django_db_blocker):
    with django_db_blocker.unblock():
      guest = factories.UserFactory(is_active=True, role=RoleType.GUEST)

    return guest

# =============
# = GenreView =
# =============
@pytest.mark.quiz
@pytest.mark.view
@pytest.mark.django_db
class TestGenreView(Common):
  list_view_url = reverse('quiz:genre_list')
  create_view_url = reverse('quiz:create_genre')
  update_view_url = lambda _self, pk: reverse('quiz:update_genre', kwargs={'pk': pk})

  def test_get_access_to_listpage(self, get_user, client):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_403_FORBIDDEN,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_user
    client.force_login(user)
    response = client.get(self.list_view_url)

    assert response.status_code == exact_types[key]

  def test_get_access_to_createpage(self, get_user, client):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_403_FORBIDDEN,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_user
    client.force_login(user)
    response = client.get(self.create_view_url)

    assert response.status_code == exact_types[key]

  @pytest.mark.parametrize([
    'name',
    'is_enabled',
  ], [
    ('hoge-cv', True),
    ('hoge-cv', False),
    ('1-cv'*32, False),
  ], ids=[
    'is-enabled',
    'is-not-enabled',
    'is-max-name-length',
  ])
  def test_post_access_to_createpage(self, get_manager, client, name, is_enabled):
    user = get_manager
    client.force_login(user)
    params = {
      'name': name,
      'is_enabled': is_enabled,
    }
    response = client.post(self.create_view_url, data=params)
    try:
      instance = models.Genre.objects.get(name=name)
    except Exception as ex:
      pytest.fail(f'Unexpected Error: {ex}')

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_view_url
    assert instance.is_enabled == is_enabled

  def test_invalid_post_request_to_createpage(self, get_manager, client):
    user = get_manager
    client.force_login(user)
    instance = factories.GenreFactory(name='hogehoge-inv-cv')
    params = {
      'name': instance.name,
      'is_enabled': False,
    }
    response = client.post(self.create_view_url, data=params)
    form = response.context['form']
    err_msg = 'Genre with this Genre name already exists.'

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(form.errors)

  def test_get_access_to_updatepage(self, get_user, client):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_403_FORBIDDEN,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_user
    client.force_login(user)
    instance = factories.GenreFactory()
    response = client.get(self.update_view_url(instance.pk))

    assert response.status_code == exact_types[key]

  def test_invalid_get_access_to_updatepage(self, get_manager, client):
    user = get_manager
    client.force_login(user)
    dummy_pk = uuid.uuid4()
    response = client.get(self.update_view_url(dummy_pk))

    assert response.status_code == status.HTTP_404_NOT_FOUND

  def test_post_access_to_updatepage(self, get_manager, client):
    user = get_manager
    client.force_login(user)
    original = factories.GenreFactory(name='hogehoge-uv', is_enabled=False)
    url = self.update_view_url(original.pk)
    params = {
      'name': 'foobar-uv',
      'is_enabled': True,
    }
    response = client.post(url, data=params)
    instance = models.Genre.objects.get(pk=original.pk)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_view_url
    assert instance.name == params['name']
    assert instance.is_enabled == params['is_enabled']

# ============
# = QuizView =
# ============
@pytest.mark.quiz
@pytest.mark.view
@pytest.mark.django_db
class TestQuizView(Common):
  list_view_url = reverse('quiz:quiz_list')
  create_view_url = reverse('quiz:create_quiz')
  update_view_url = lambda _self, pk: reverse('quiz:update_quiz', kwargs={'pk': pk})
  delete_view_url = lambda _self, pk: reverse('quiz:delete_quiz', kwargs={'pk': pk})

  @pytest.fixture
  def get_genres(self, django_db_blocker):
    with django_db_blocker.unblock():
      genres = list(factories.GenreFactory.create_batch(2, is_enabled=True))

    return genres

  def test_get_access_to_listpage(self, get_user, client):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_200_OK,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_user
    client.force_login(user)
    response = client.get(self.list_view_url)

    assert response.status_code == exact_types[key]

  @pytest.mark.parametrize([
    'role',
    'is_staff',
    'is_superuser',
  ], [
    (RoleType.GUEST, True, True),
    (RoleType.MANAGER, False, False),
    (RoleType.CREATOR, False, False),
  ], ids=[
    'is-superuser',
    'is-manager',
    'is-creator',
  ])
  def test_queryset_method_in_listpage(self, get_genres, rf, role, is_staff, is_superuser):
    genres = get_genres
    user = factories.UserFactory(is_active=True, role=role, is_staff=is_staff, is_superuser=is_superuser)
    other_creator = factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    _ = factories.QuizFactory(creator=other_creator, genre=genres[0], is_completed=True)
    _ = factories.QuizFactory(creator=other_creator, genre=genres[0], is_completed=False)
    if role == RoleType.CREATOR:
      _ = factories.QuizFactory.create_batch(2, creator=user, genre=genres[0], is_completed=True)
      _ = factories.QuizFactory.create_batch(3, creator=user, genre=genres[0], is_completed=False)
      expected_count = 5
    else:
      expected_count = len(models.Quiz.objects.all())
    # Call `get_queryset` method
    request = rf.get(self.list_view_url)
    request.user = user
    view = views.QuizListPage()
    view.setup(request)
    queryset = view.get_queryset()

    assert len(queryset) == expected_count

  def test_get_access_to_createpage(self, get_user, client):
    exact_types = {
      'superuser': status.HTTP_403_FORBIDDEN,
      'manager': status.HTTP_403_FORBIDDEN,
      'creator': status.HTTP_200_OK,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_user
    client.force_login(user)
    response = client.get(self.create_view_url)

    assert response.status_code == exact_types[key]

  def test_post_access_to_createpage(self, client):
    genre = factories.GenreFactory(name='quiz-cv-for-creator')
    user = factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    params = {
      'genre': str(genre.pk),
      'question': 'hogehoge',
      'answer': 'fugafuga',
      'is_completed': True,
    }
    client.force_login(user)
    response = client.post(self.create_view_url, data=params)
    try:
      instance = models.Quiz.objects.get(creator=user, genre=genre)
    except Exception as ex:
      pytest.fail(f'Unexpected Error: {ex}')

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_view_url
    assert instance.genre.pk == genre.pk
    assert instance.question == params['question']
    assert instance.answer == params['answer']
    assert instance.is_completed == params['is_completed']

  def test_invalid_post_request_to_createpage(self, client):
    # Target genre is not enabled
    invalid_genre = factories.GenreFactory(name='quiz-cv-and-invalid-post', is_enabled=False)
    user = factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    params = {
      'genre': str(invalid_genre.pk),
      'question': 'hogehoge',
      'answer': 'fugafuga',
      'is_completed': True,
    }
    client.force_login(user)
    response = client.post(self.create_view_url, data=params)
    form = response.context['form']
    err_msg = 'Select a valid choice. That choice is not one of the available choices.'

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(form.errors)

  @pytest.mark.parametrize([
    'role',
    'is_staff',
    'is_superuser',
    'is_owner',
    'status_code',
  ], [
    (RoleType.GUEST, True, True, False, status.HTTP_200_OK),
    (RoleType.MANAGER, False, False, False, status.HTTP_200_OK),
    (RoleType.CREATOR, False, False, True, status.HTTP_200_OK),
    (RoleType.CREATOR, False, False, False, status.HTTP_403_FORBIDDEN),
    (RoleType.GUEST, False, False, False, status.HTTP_403_FORBIDDEN),
  ], ids=[
    'is-superuser',
    'is-manager',
    'is-creator-with-own-quiz',
    'is-creator-without-own-quiz',
    'is-guest',
  ])
  def test_get_access_to_updatepage(self, get_genres, client, role, is_staff, is_superuser, is_owner, status_code):
    genres = get_genres
    user = factories.UserFactory(is_active=True, role=role, is_staff=is_staff, is_superuser=is_superuser)
    creator = user if is_owner else factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    instance = factories.QuizFactory(creator=creator, genre=genres[0])
    client.force_login(user)
    response = client.get(self.update_view_url(instance.pk))

    assert response.status_code == status_code

  @pytest.mark.parametrize([
    'role',
    'is_staff',
    'is_superuser',
    'is_owner',
  ], [
    (RoleType.GUEST, True, True, False),
    (RoleType.MANAGER, False, False, False),
    (RoleType.CREATOR, False, False, True),
  ], ids=[
    'is-superuser',
    'is-manager',
    'is-creator',
  ])
  def test_post_access_to_updatepage(self, get_genres, client, role, is_staff, is_superuser, is_owner):
    genres = get_genres
    user = factories.UserFactory(is_active=True, role=role, is_staff=is_staff, is_superuser=is_superuser)
    creator = user if is_owner else factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    original = factories.QuizFactory(creator=creator, genre=genres[0], is_completed=False)
    client.force_login(user)
    url = self.update_view_url(original.pk)
    params = {
      'genre': str(original.genre.pk),
      'answer': 'fugafuga-in-updat-view',
      'is_completed': True,
    }
    response = client.post(url, data=params)
    try:
      instance = models.Quiz.objects.get(pk=original.pk)
    except Exception as ex:
      pytest.fail(f'Unexpected Error: {ex}')

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_view_url
    assert instance.creator.pk == original.creator.pk
    assert instance.genre.pk == original.genre.pk
    assert instance.question == ''
    assert instance.answer == params['answer']
    assert instance.is_completed == params['is_completed']

  def test_invalid_post_request_to_updatepage(self, get_genres, client):
    genres = get_genres
    user = factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    invalid_genre = factories.GenreFactory(is_enabled=False)
    instance = factories.QuizFactory(creator=user, genre=genres[0])
    client.force_login(user)
    url = self.update_view_url(instance.pk)
    params = {
      'genre': str(invalid_genre.pk),
    }
    response = client.post(url, data=params)
    form = response.context['form']
    err_msg = 'Select a valid choice. That choice is not one of the available choices.'

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(form.errors)

  @pytest.mark.parametrize([
    'is_owner',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'is-owner',
    'is-not-owner',
  ])
  def test_get_access_to_deletepage(self, get_genres, get_user, client, is_owner):
    key, user = get_user
    genres = get_genres
    expected_type = {
      'superuser': status.HTTP_405_METHOD_NOT_ALLOWED,
      'manager': status.HTTP_405_METHOD_NOT_ALLOWED,
      'creator': status.HTTP_405_METHOD_NOT_ALLOWED if is_owner else status.HTTP_403_FORBIDDEN,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    expected_status_code = expected_type[key]
    creator = user if is_owner and user.is_creator() else factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    instance = factories.QuizFactory(creator=creator, genre=genres[0])
    client.force_login(user)
    response = client.get(self.delete_view_url(instance.pk))

    assert response.status_code == expected_status_code

  @pytest.mark.parametrize([
    'is_completed',
    'is_owner',
  ], [
    (True, True),
    (True, False),
    (False, True),
  ], ids=[
    'is-completed-and-owner',
    'is-completed-and-other',
    'is-not-completed',
  ])
  def test_post_access_to_deletepage(self, get_genres, get_user, client, is_completed, is_owner):
    exact_types = {
      'superuser': status.HTTP_302_FOUND,
      'manager': status.HTTP_302_FOUND,
      'creator': status.HTTP_302_FOUND if is_owner else status.HTTP_403_FORBIDDEN,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    exact_counts = {
      'superuser': 0,
      'manager': 0,
      'creator': 0 if is_owner else 1,
      'guest': 1,
    }
    key, user = get_user
    genres = get_genres
    creator = user if key == 'creator' and is_owner else factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    instance = factories.QuizFactory(creator=creator, genre=genres[0], is_completed=is_completed)
    expected_status_code = exact_types[key]
    expected_count = exact_counts[key]
    client.force_login(user)
    response = client.post(self.delete_view_url(instance.pk))
    queryset = models.Quiz.objects.filter(pk__in=[instance.pk])

    assert response.status_code == expected_status_code
    assert len(queryset) == expected_count

# ================
# = QuizRoomView =
# ================
@pytest.mark.quiz
@pytest.mark.view
@pytest.mark.django_db
class TestQuizRoomView(Common):
  pk_convertor = lambda _self, xs: [val.pk for val in xs]
  compare_qs = lambda _self, qs, exacts: all([val.pk == exact.pk for val, exact in zip(qs, exacts)])
  list_view_url = reverse('quiz:room_list')
  create_view_url = reverse('quiz:create_room')
  update_view_url = lambda _self, pk: reverse('quiz:update_room', kwargs={'pk': pk})
  delete_view_url = lambda _self, pk: reverse('quiz:delete_room', kwargs={'pk': pk})
  detail_view_url = lambda _self, pk: reverse('quiz:enter_room', kwargs={'pk': pk})

  def test_get_access_to_listpage(self, get_user, client):
    _, user = get_user
    client.force_login(user)
    response = client.get(self.list_view_url)

    assert response.status_code == status.HTTP_200_OK

  @pytest.mark.parametrize([
    'role',
    'is_staff',
    'is_superuser',
  ], [
    (RoleType.GUEST, True, True),
    (RoleType.MANAGER, False, False),
    (RoleType.CREATOR, False, False),
    (RoleType.GUEST, False, False),
  ], ids=[
    'is-superuser',
    'is-manager',
    'is-creator',
    'is-guest',
  ])
  def test_queryset_method_in_listpage(self, rf, role, is_staff, is_superuser):
    user = factories.UserFactory(is_active=True, role=role, is_staff=is_staff, is_superuser=is_superuser)
    other_creators = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.CREATOR)
    other_guests = factories.UserFactory.create_batch(2, is_active=True, role=RoleType.GUEST)
    # ========================
    # = Create several rooms =
    # ========================
    # Case 1: The current user is not assigned (There are three patterns)
    _ = factories.QuizRoomFactory(owner=other_creators[0], members=self.pk_convertor(other_guests), is_enabled=True)
    _ = factories.QuizRoomFactory(owner=other_creators[1], members=self.pk_convertor([other_guests[0]]), is_enabled=True)
    _ = factories.QuizRoomFactory(owner=other_creators[1], members=self.pk_convertor([other_guests[1]]), is_enabled=False)
    _ = factories.QuizRoomFactory(owner=other_creators[1], members=self.pk_convertor(other_guests), is_enabled=False)
    _ = factories.QuizRoomFactory(owner=other_creators[2], members=self.pk_convertor([other_guests[1]]), is_enabled=False)
    # Case 2: The current user is assigned to other user's room (There are two patterns)
    if user.is_player():
      _ = factories.QuizRoomFactory(owner=other_creators[0], members=self.pk_convertor([other_guests[0], user]), is_enabled=True)
      _ = factories.QuizRoomFactory(owner=other_creators[2], members=self.pk_convertor([other_creators[0], user]), is_enabled=False)
    # Case 3: The current user is owner of the room
    if user.is_player():
      _ = factories.QuizRoomFactory(owner=user, members=self.pk_convertor([other_guests[0], other_creators[0]]), is_enabled=True)
      _ = factories.QuizRoomFactory(owner=user, members=self.pk_convertor([other_guests[1], other_creators[1]]), is_enabled=True)
      _ = factories.QuizRoomFactory(owner=user, members=self.pk_convertor([other_creators[1]]), is_enabled=False)

    # ==================
    # = Get exact data =
    # ==================
    if user.is_player():
      expected_count = models.QuizRoom.objects.filter(Q(owner=user) | Q(members__pk__in=[user.pk], is_enabled=True)).order_by('pk').distinct().count()
    else:
      expected_count = models.QuizRoom.objects.all().count()

    # Call `get_queryset` method
    request = rf.get(self.list_view_url)
    request.user = user
    view = views.QuizRoomListPage()
    view.setup(request)
    queryset = view.get_queryset()

    assert len(queryset) == expected_count

  def test_get_access_to_createpage(self, get_user, client):
    exact_types = {
      'superuser': status.HTTP_403_FORBIDDEN,
      'manager': status.HTTP_403_FORBIDDEN,
      'creator': status.HTTP_200_OK,
      'guest': status.HTTP_200_OK,
    }
    key, user = get_user
    client.force_login(user)
    response = client.get(self.create_view_url)

    assert response.status_code == exact_types[key]

  @pytest.fixture
  def get_querysets(self, django_db_blocker, mocker):
    with django_db_blocker.unblock():
      creators = factories.UserFactory.create_batch(5, is_active=True, role=RoleType.CREATOR)
      creators = UserModel.objects.filter(pk__in=self.pk_convertor(creators)).order_by('pk')
      guests = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.GUEST)
      members = UserModel.objects.filter(pk__in=self.pk_convertor(list(creators) + guests)).order_by('pk')
      genres = factories.GenreFactory.create_batch(2, is_enabled=True)
      genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).order_by('pk')
    # Mock
    mocker.patch('quiz.models.GenreQuerySet.collect_active_genres', return_value=genres)
    mocker.patch('account.models.CustomUserManager.collect_creators', return_value=creators)
    mocker.patch('account.models.CustomUserManager.collect_valid_normal_users', return_value=members)

    return genres, creators, members

  @pytest.mark.parametrize([
    'role',
  ], [
    (RoleType.CREATOR, ),
    (RoleType.GUEST, ),
  ], ids=[
    'is-creator',
    'is-guest',
  ])
  def test_post_access_to_createpage(self, get_querysets, client, role):
    user = factories.UserFactory(is_active=True, role=role)
    genres, creators, members = get_querysets
    # Define post data
    params = {
      'name': 'hoge-room',
      'genres': self.pk_convertor(genres),
      'creators': self.pk_convertor(creators),
      'members': self.pk_convertor(members),
      'max_question': 123,
      'is_enabled': True,
    }
    client.force_login(user)
    response = client.post(self.create_view_url, data=params)
    try:
      instance = models.QuizRoom.objects.get(
        name=params['name'],
        max_question=params['max_question'],
        is_enabled=params['is_enabled'],
      )
    except Exception as ex:
      pytest.fail(f'Unexpected Error: {ex}')
    all_genres = instance.genres.all().order_by('pk')
    all_creators = instance.creators.all().order_by('pk')
    all_members = instance.members.all().order_by('pk')

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_view_url
    assert len(all_genres) == len(genres)
    assert self.compare_qs(all_genres, genres.order_by('pk'))
    assert len(all_creators) == len(creators)
    assert self.compare_qs(all_creators, creators.order_by('pk'))
    assert len(all_members) == len(members)
    assert self.compare_qs(all_members, members.order_by('pk'))

  @pytest.mark.parametrize([
    'is_owner',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'is-owner',
    'is-not-owner',
  ])
  def test_get_access_to_updatepage(self, get_user, get_querysets, client, is_owner):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_200_OK if is_owner else status.HTTP_403_FORBIDDEN,
      'guest': status.HTTP_200_OK if is_owner else status.HTTP_403_FORBIDDEN,
    }
    key, user = get_user
    owner = user if is_owner else factories.UserFactory(is_active=True, role=user.role)
    genres, creators, members = get_querysets
    instance = factories.QuizRoomFactory(
      owner=owner,
      genres=list(genres),
      creators=list(creators),
      members=list(members),
      is_enabled=False,
    )
    client.force_login(user)
    response = client.get(self.update_view_url(instance.pk))

    assert response.status_code == exact_types[key]

  def test_post_access_to_updatepage(self, get_user, get_querysets, client):
    _, user = get_user
    owner = user if user.is_player() else factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    genres, creators, members = get_querysets
    original = factories.QuizRoomFactory(
      owner=owner,
      genres=list(genres),
      creators=list(creators),
      members=list(members),
      is_enabled=False,
    )
    # Form submit
    client.force_login(user)
    url = self.update_view_url(original.pk)
    params = {
      'name': 'updated-name',
      'creators': [str(creators[0].pk), str(creators[1].pk)],
      'members': [str(user.pk) for user in members],
      'max_question': 10,
      'is_enabled': True,
    }
    response = client.post(url, data=params)
    try:
      instance = models.QuizRoom.objects.get(pk=original.pk)
    except Exception as ex:
      pytest.fail(f'Unexpected Error: {ex}')
    all_genres = instance.genres.all().order_by('pk')
    all_creators = instance.creators.all().order_by('pk')
    all_members = instance.members.all().order_by('pk')

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == self.list_view_url
    assert instance.owner.pk == original.owner.pk
    assert instance.name == params['name']
    assert len(all_genres) == 0
    assert len(all_creators) == len(params['creators'])
    assert len(all_members) == len(params['members'])
    assert self.compare_qs(all_creators, UserModel.objects.filter(pk__in=params['creators']).order_by('pk'))
    assert self.compare_qs(all_members, members)
    assert instance.max_question == params['max_question']
    assert instance.is_enabled == params['is_enabled']

  @pytest.mark.parametrize([
    'data_type',
  ], [
    ('both-genres-and-creators-are-none', ),
    ('set-invalid-creator', ),
    ('set-invalid-genre', ),
    ('set-invalid-member', ),
  ], ids=[
    'invalid-genres-and-creators',
    'invalid-creator',
    'invalid-genre',
    'invalid-member',
  ])
  def test_invalid_post_request_to_updatepage(self, get_querysets, client, data_type):
    user = factories.UserFactory(is_active=True, role=RoleType.GUEST)
    genres, creators, members = get_querysets
    original = factories.QuizRoomFactory(
      owner=user,
      genres=list(genres),
      creators=list(creators),
      members=list(members),
      is_enabled=False,
    )
    # Form submit
    client.force_login(user)
    url = self.update_view_url(original.pk)
    params = {
      'name': 'updated-name',
      'genres': [str(genres[0].pk)],
      'creators': [str(creators[0].pk)],
      'members': [str(members[0].pk)],
      'max_question': 10,
      'is_enabled': True,
    }
    if data_type == 'both-genres-and-creators-are-none':
      params['genres'] = []
      params['creators'] = []
      err_msg = 'You have to assign at least one of genres and creators to the quiz room.'
    elif data_type == 'set-invalid-creator':
      other = factories.UserFactory(is_active=True, role=RoleType.CREATOR)
      params['creators'] = [str(other.pk)]
      err_msg = f'Select a valid choice. {other.pk} is not one of the available choices.'
    elif data_type == 'set-invalid-genre':
      other = factories.GenreFactory(is_enabled=False)
      params['genres'] = [str(other.pk)]
      err_msg = f'Select a valid choice. {other.pk} is not one of the available choices.'
    elif data_type == 'set-invalid-member':
      other = factories.UserFactory(is_active=True, role=RoleType.GUEST)
      params['members'] = [str(other.pk)]
      err_msg = f'Select a valid choice. {other.pk} is not one of the available choices.'
    response = client.post(url, data=params)
    form = response.context['form']

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(form.errors)

  @pytest.mark.parametrize([
    'is_owner',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'is-owner',
    'is-not-owner',
  ])
  def test_get_access_to_deletepage(self, get_user, get_querysets, client, is_owner):
    _, user = get_user
    can_access = is_owner and user.is_player()
    genres, creators, members = get_querysets
    owner = user if can_access else factories.UserFactory(is_active=True, role=RoleType.GUEST)
    instance = factories.QuizRoomFactory(
      owner=owner,
      genres=list(genres),
      creators=list(creators),
      members=list(members),
      is_enabled=True,
    )
    client.force_login(user)
    response = client.get(self.delete_view_url(instance.pk))

    assert response.status_code == status.HTTP_403_FORBIDDEN

  @pytest.mark.parametrize([
    'is_enabled',
    'is_owner',
  ], [
    (True, True),
    (True, False),
    (False, True),
  ], ids=[
    'is-enabled-and-owner',
    'is-enabled-and-other',
    'is-not-enabled',
  ])
  def test_post_access_to_deletepage(self, get_user, get_querysets, client, is_enabled, is_owner):
    can_delete_for_having_manager_role = not is_enabled
    can_delete_for_player = is_owner and not is_enabled
    exact_flags = {
      'superuser': can_delete_for_having_manager_role,
      'manager': can_delete_for_having_manager_role,
      'creator': can_delete_for_player,
      'guest': can_delete_for_player,
    }
    key, user = get_user
    genres, creators, members = get_querysets
    owner = user if is_owner else factories.UserFactory(is_active=True, role=RoleType.GUEST)
    instance = factories.QuizRoomFactory(
      owner=owner,
      genres=list(genres),
      creators=list(creators),
      members=list(members),
      is_enabled=is_enabled,
    )
    if exact_flags[key]:
      expected_status_code = status.HTTP_302_FOUND
      expected_count = 0
    else:
      expected_status_code = status.HTTP_403_FORBIDDEN
      expected_count = 1
    client.force_login(user)
    response = client.post(self.delete_view_url(instance.pk))
    queryset = models.QuizRoom.objects.filter(pk__in=[instance.pk])

    assert response.status_code == expected_status_code
    assert len(queryset) == expected_count

  @pytest.mark.parametrize([
    'is_owner',
    'is_assigned',
    'is_enabled',
  ], [
    (True, True, False),
    (True, False, True),
    (True, False, False),
    (False, True, True),
    (False, True, False),
    (False, False, True),
  ], ids=[
    'cannot-access',
    'is-owner-and-can-access',
    'is-owner-and-cannot-access',
    'is-assigned-and-can-access',
    'is-assigned-and-cannot-access',
    'invalid-user',
  ])
  def test_get_access_to_detailpage(self, get_user, client, is_owner, is_assigned, is_enabled):
    can_access = (is_owner or is_assigned) and is_enabled
    expected_type = {
      'superuser': status.HTTP_403_FORBIDDEN,
      'manager': status.HTTP_403_FORBIDDEN,
      'creator': status.HTTP_200_OK if can_access else status.HTTP_403_FORBIDDEN,
      'guest': status.HTTP_200_OK if can_access else status.HTTP_403_FORBIDDEN,
    }
    key, user = get_user
    genres = factories.GenreFactory.create_batch(2, is_enabled=True)
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).order_by('pk')
    creators = factories.UserFactory.create_batch(5, is_active=True, role=RoleType.CREATOR)
    creators = UserModel.objects.filter(pk__in=self.pk_convertor(creators)).order_by('pk')
    guests = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.GUEST)
    members = (list(creators) + guests + [user]) if is_assigned and user.is_player() else (list(creators) + guests)
    members = UserModel.objects.filter(pk__in=self.pk_convertor(members)).order_by('pk')
    owner = user if is_owner and user.is_player() else factories.UserFactory(is_active=True, role=RoleType.GUEST)
    instance = factories.QuizRoomFactory(
      owner=owner,
      genres=list(genres),
      creators=list(creators),
      members=list(members),
      is_enabled=is_enabled,
    )
    expected_status_code = expected_type[key]
    client.force_login(user)
    response = client.get(self.detail_view_url(instance.pk))

    assert response.status_code == expected_status_code

  def test_context_method_in_detailpage(self, get_querysets, rf):
    user = factories.UserFactory(is_active=True, role=RoleType.GUEST)
    genres, creators, members = get_querysets
    instance = factories.QuizRoomFactory(
      owner=user,
      name='hoge-room',
      genres=list(genres),
      creators=list(creators),
      members=list(members),
      is_enabled=True,
    )
    request = rf.get(self.detail_view_url(instance.pk))
    request.user = user
    view = views.EnterQuizRoom()
    # Setup view instance
    view.setup(request)
    view.object = instance
    # Call test method
    context = view.get_context_data()

    assert view.crumbles[-1].title == 'hoge-room'