import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
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
import json
import tempfile
import uuid
import urllib.parse

UserModel = get_user_model()

class Common:
  pk_convertor = lambda _self, xs: [item.pk for item in xs]
  compare_qs = lambda _self, qs, exacts: all([val.pk == exact.pk for val, exact in zip(qs, exacts)])

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

  def test_get_access_to_listpage(self, get_users, client):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_403_FORBIDDEN,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_users
    client.force_login(user)
    response = client.get(self.list_view_url)

    assert response.status_code == exact_types[key]

  def test_get_access_to_createpage(self, get_users, client):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_403_FORBIDDEN,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_users
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

  def test_get_access_to_updatepage(self, get_genres, get_users, client):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_403_FORBIDDEN,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_users
    client.force_login(user)
    instance = get_genres[0]
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

  @pytest.mark.parametrize([
    'updated_name',
  ], [
    ('hogehoge-uv', ),
    ('foobar-uv', ),
  ], ids=[
    'same-name',
    'different-name',
  ])
  def test_invalid_post_request_in_updatepage(self, get_manager, get_creator, client, updated_name):
    user = get_manager
    creator = get_creator
    client.force_login(user)
    genre = factories.GenreFactory(name='hogehoge-uv', is_enabled=True)
    _ = factories.QuizFactory(creator=creator, genre=genre, is_completed=True)
    url = self.update_view_url(genre.pk)
    params = {
      'name': updated_name,
      'is_enabled': False,
    }
    response = client.post(url, data=params)
    form = response.context['form']
    err_msg = 'There is at least one quiz but this genre status is set to &quot;Disable&quot;.'

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(form.errors)

# ============
# = QuizView =
# ============
@pytest.fixture(scope='class')
def get_specific_quizzes(django_db_blocker, get_genres):
  with django_db_blocker.unblock():
    genres = get_genres[:3]
    creators = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.CREATOR)
    # Create instance
    instances = []
    for genre in genres:
      instances += [factories.QuizFactory(creator=creators[0], genre=genre, is_completed=False)]

      for creator in creators:
        instances += [
          factories.QuizFactory(creator=creator, genre=genre, is_completed=True),
          factories.QuizFactory(creator=creator, genre=genre, is_completed=False),
        ]

  return genres, creators, instances

@pytest.mark.quiz
@pytest.mark.view
@pytest.mark.django_db
class TestQuizView(Common):
  list_view_url = reverse('quiz:quiz_list')
  create_view_url = reverse('quiz:create_quiz')
  update_view_url = lambda _self, pk: reverse('quiz:update_quiz', kwargs={'pk': pk})
  delete_view_url = lambda _self, pk: reverse('quiz:delete_quiz', kwargs={'pk': pk})
  paginate_by = 15

  def test_get_access_to_listpage(self, get_users, client):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_200_OK,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_users
    client.force_login(user)
    response = client.get(self.list_view_url)

    assert response.status_code == exact_types[key]

  def test_queryset_method_in_listpage(self, get_has_creator_role_users, get_genres, rf, mocker):
    genres = get_genres
    _, user = get_has_creator_role_users
    # Check user role
    if user.is_creator():
      quizzes = [
        *factories.QuizFactory.create_batch(2, creator=user, genre=genres[0], is_completed=True),
        *factories.QuizFactory.create_batch(3, creator=user, genre=genres[0], is_completed=False)
      ]
      quizzes = models.Quiz.objects.filter(pk__in=self.pk_convertor(quizzes))
      # Mock for related_name's elements
      mock_user = mocker.patch('account.models.User', side_effect=UserModel())
      mock_user.quizzes.all.return_value = quizzes
      expected_count = 5
    else:
      other_creator = factories.UserFactory(is_active=True, role=RoleType.CREATOR)
      quizzes = [
        factories.QuizFactory(creator=other_creator, genre=genres[0], is_completed=True),
        factories.QuizFactory(creator=other_creator, genre=genres[0], is_completed=False)
      ]
      quizzes = models.Quiz.objects.filter(pk__in=self.pk_convertor(quizzes))
      mocker.patch('quiz.models.QuizQuerySet.select_related', return_value=quizzes)
      expected_count = 2
    # Call `get_queryset` method
    request = rf.get(self.list_view_url)
    request.user = user
    view = views.QuizListPage()
    view.setup(request)
    queryset = view.get_queryset()

    assert queryset.count() == expected_count

  @pytest.mark.parametrize([
    'has_manager_role',
    'is_and_op',
  ], [
    (False, True),
    (False, False),
    (True, True),
    (True, False),
  ], ids=[
    'is-creator-and-condition',
    'is-creator-or-condition',
    'is-manager-and-condition',
    'is-manager-or-condition',
  ])
  def test_post_reqeust_to_extract_queryset(self, get_specific_quizzes, mocker, client, has_manager_role, is_and_op):
    genres, creators, instances = get_specific_quizzes
    user = creators[0] if not has_manager_role else factories.UserFactory(is_active=True, role=RoleType.MANAGER)
    # Create parameters
    all_queryset = models.Quiz.objects.filter(pk__in=self.pk_convertor(instances))
    if not has_manager_role:
      all_queryset = all_queryset.filter(creator=creators[0])
    mocker.patch('quiz.views.QuizListPage.get_queryset', return_value=all_queryset)
    params = {
      'genres': [str(genres[1].pk), str(genres[2].pk)],
      'creators': [str(creators[1].pk), str(creators[2].pk)] if has_manager_role else [],
      'is_and_op': is_and_op,
    }
    if has_manager_role:
      selected_qs = models.Quiz.objects.collect_quizzes(
        queryset=all_queryset,
        creators=params['creators'],
        genres=params['genres'],
        is_and_op=is_and_op,
      )
    else:
      del params['creators']
      selected_qs = models.Quiz.objects.collect_quizzes(
        queryset=all_queryset,
        genres=params['genres'],
        is_and_op=is_and_op,
      )
    # Check output
    client.force_login(user)
    response = client.post(self.list_view_url, data=params, follow=True)
    quizzes = response.context['quizzes']
    estimated = models.Quiz.objects.filter(pk__in=[_quiz.pk for _quiz in quizzes]).order_by('pk')
    expected = selected_qs[:self.paginate_by] if len(selected_qs) > self.paginate_by else selected_qs
    expected = models.Quiz.objects.filter(pk__in=self.pk_convertor(expected)).order_by('pk')

    assert response.status_code == status.HTTP_200_OK
    assert estimated.count() == len(expected)
    assert self.compare_qs(estimated, expected)

  def test_invalid_post_reqeust_to_extract_queryset(self, get_specific_quizzes, get_manager, mocker, client):
    genres, creators, instances = get_specific_quizzes
    user = get_manager
    # Create parameters
    all_queryset = models.Quiz.objects.filter(pk__in=self.pk_convertor(instances)).order_by('pk')
    mocker.patch('quiz.views.QuizListPage.get_queryset', return_value=all_queryset)
    params = {
      'genres': [str(genres[1].pk), str(genres[2].pk)],
      'creators': [str(creators[1].pk), str(creators[2].pk)],
    }
    # Check output
    client.force_login(user)
    response = client.post(self.list_view_url, data=params, follow=True)
    quizzes = response.context['quizzes']
    estimated = models.Quiz.objects.filter(pk__in=[_quiz.pk for _quiz in quizzes]).order_by('pk')
    expected = all_queryset[:self.paginate_by] if len(all_queryset) > self.paginate_by else all_queryset

    assert response.status_code == status.HTTP_200_OK
    assert estimated.count() == len(expected)
    assert self.compare_qs(estimated, expected)

  def test_get_access_to_createpage(self, get_users, client):
    exact_types = {
      'superuser': status.HTTP_403_FORBIDDEN,
      'manager': status.HTTP_403_FORBIDDEN,
      'creator': status.HTTP_200_OK,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_users
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

  def test_get_access_to_updatepage(self, get_genres, client, get_members_with_owner):
    patterns = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_403_FORBIDDEN,
      'guest': status.HTTP_403_FORBIDDEN,
      'owner': status.HTTP_200_OK,
    }
    genres = get_genres
    key, user = get_members_with_owner(RoleType.CREATOR)
    creator = user if key == 'owner' else factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    instance = factories.QuizFactory(creator=creator, genre=genres[0])
    client.force_login(user)
    response = client.get(self.update_view_url(instance.pk))
    status_code = patterns[key]

    assert response.status_code == status_code

  def test_post_access_to_updatepage(self, get_genres, client, get_has_creator_role_users):
    genres = get_genres
    key, user = get_has_creator_role_users
    creator = user if key == 'creator' else factories.UserFactory(is_active=True, role=RoleType.CREATOR)
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

  def test_invalid_post_request_to_updatepage(self, get_genres, get_creator, client):
    genres = get_genres
    user = get_creator
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
  def test_get_access_to_deletepage(self, get_genres, get_users, client, is_owner):
    key, user = get_users
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
  def test_post_access_to_deletepage(self, get_genres, get_users, client, is_completed, is_owner):
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
    key, user = get_users
    genres = get_genres
    creator = user if key == 'creator' and is_owner else factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    instance = factories.QuizFactory(creator=creator, genre=genres[0], is_completed=is_completed)
    expected_status_code = exact_types[key]
    expected_count = exact_counts[key]
    client.force_login(user)
    response = client.post(self.delete_view_url(instance.pk))
    queryset = models.Quiz.objects.filter(pk__in=[instance.pk])

    assert response.status_code == expected_status_code
    assert queryset.count() == expected_count

# ================
# = QuizRoomView =
# ================
@pytest.mark.quiz
@pytest.mark.view
@pytest.mark.django_db
class TestQuizRoomView(Common):
  list_view_url = reverse('quiz:room_list')
  create_view_url = reverse('quiz:create_room')
  update_view_url = lambda _self, pk: reverse('quiz:update_room', kwargs={'pk': pk})
  delete_view_url = lambda _self, pk: reverse('quiz:delete_room', kwargs={'pk': pk})
  detail_view_url = lambda _self, pk: reverse('quiz:enter_room', kwargs={'pk': pk})

  def test_get_access_to_listpage(self, get_users, client):
    _, user = get_users
    client.force_login(user)
    response = client.get(self.list_view_url)

    assert response.status_code == status.HTTP_200_OK

  def test_queryset_method_in_listpage(self, rf, get_users):
    _, user = get_users
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

    assert queryset.count() == expected_count

  @pytest.mark.parametrize([
    'name',
    'is_player',
    'count',
  ], [
    ('hoge-room', True, 1),
    ('hoge-room', False, 1),
    ('room', True, 2),
    ('room', False, 3),
    ('no-room', True, 0),
    ('no-room', False, 0),
  ], ids=[
    'only-one-room-and-player',
    'only-one-room-and-not-player',
    'two-rooms-and-player',
    'two-rooms-and-not-player',
    'no-rooms-and-player',
    'no-rooms-and-not-player',
  ])
  def test_filtering_method_in_listpage(self, get_genres, mocker, client, name, is_player, count):
    if is_player:
      user = factories.UserFactory(is_active=True, role=RoleType.GUEST)
      player = user
    else:
      user = factories.UserFactory(is_active=True, role=RoleType.MANAGER)
      player = factories.UserFactory(is_active=True, role=RoleType.GUEST)
    others = factories.UserFactory.create_batch(2, is_active=True, role=RoleType.GUEST)
    genres = get_genres
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).order_by('-pk')
    player_rooms = [
      factories.QuizRoomFactory(owner=player, name='hoge-room', genres=genres, members=[]),
      factories.QuizRoomFactory(owner=others[0], name='foo-room', genres=genres, members=[player]),
      factories.QuizRoomFactory(owner=player, name='not-relevant-instance', genres=genres, members=[]),
      factories.QuizRoomFactory(owner=others[0], name='ignore-instance', genres=genres, members=[player]),
    ]
    rest_rooms = [
      factories.QuizRoomFactory(owner=others[1], name='bar-room', genres=genres, members=[others[0]]),
      factories.QuizRoomFactory(owner=others[1], name='not-target-player', genres=genres, members=[others[0]]),
    ]
    all_queryset = models.QuizRoom.objects.filter(pk__in=self.pk_convertor(player_rooms+rest_rooms))
    if is_player:
      target_qs = models.QuizRoom.objects.filter(pk__in=self.pk_convertor(player_rooms))
      mocker.patch('quiz.models.QuizRoom.objects.collect_relevant_rooms', return_value=target_qs)
    else:
      mocker.patch('quiz.models.QuizRoom.objects.collect_relevant_rooms', return_value=all_queryset)
    query_string = {
      'name': name,
    }
    # Send request
    client.force_login(user)
    response = client.get(self.list_view_url, query_params=query_string)
    output_rooms = response.context['rooms']
    estimated = models.QuizRoom.objects.filter(pk__in=[_room.pk for _room in output_rooms])

    assert response.status_code == status.HTTP_200_OK
    assert estimated.count() == count

  def test_get_access_to_createpage(self, get_users, client):
    exact_types = {
      'superuser': status.HTTP_403_FORBIDDEN,
      'manager': status.HTTP_403_FORBIDDEN,
      'creator': status.HTTP_200_OK,
      'guest': status.HTTP_200_OK,
    }
    key, user = get_users
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
      # Make quiz
      for genre in genres:
        _ = factories.QuizFactory(creator=creators[0], genre=genre, is_completed=True)
        _ = factories.QuizFactory(creator=creators[1], genre=genre, is_completed=True)
        _ = factories.QuizFactory(creator=creators[2], genre=genre, is_completed=True)
    # Mock
    mocker.patch('quiz.models.GenreQuerySet.collect_valid_genres', return_value=genres)
    mocker.patch('account.models.CustomUserManager.collect_valid_creators', return_value=creators)
    mocker.patch('account.models.CustomUserManager.collect_valid_normal_users', return_value=members)

    return genres, creators, members

  def test_post_access_to_createpage(self, get_querysets, client, get_players):
    _, user = get_players
    genres, creators, members = get_querysets
    # Define post data
    params = {
      'name': 'hoge-room',
      'genres': self.pk_convertor(genres),
      'creators': self.pk_convertor(creators),
      'members': self.pk_convertor(members),
      'max_question': 4,
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
    assert all_genres.count() == genres.count()
    assert self.compare_qs(all_genres, genres.order_by('pk'))
    assert all_creators.count() == creators.count()
    assert self.compare_qs(all_creators, creators.order_by('pk'))
    assert all_members.count() == members.count()
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
  def test_get_access_to_updatepage(self, get_users, get_querysets, client, is_owner):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_200_OK if is_owner else status.HTTP_403_FORBIDDEN,
      'guest': status.HTTP_200_OK if is_owner else status.HTTP_403_FORBIDDEN,
    }
    key, user = get_users
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

  def test_post_access_to_updatepage(self, get_users, get_querysets, client):
    _, user = get_users
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
      'max_question': 3,
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
    assert all_genres.count() == 0
    assert all_creators.count() == len(params['creators'])
    assert all_members.count() == len(params['members'])
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
      'max_question': 3,
      'is_enabled': True,
    }
    if data_type == 'both-genres-and-creators-are-none':
      params['genres'] = []
      params['creators'] = []
      err_msg = 'You have to assign at least one of genres or creators to the quiz room.'
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
  def test_get_access_to_deletepage(self, get_users, get_querysets, client, is_owner):
    _, user = get_users
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
  def test_post_access_to_deletepage(self, get_users, get_querysets, client, is_enabled, is_owner):
    can_delete_for_having_manager_role = not is_enabled
    can_delete_for_player = is_owner and not is_enabled
    exact_flags = {
      'superuser': can_delete_for_having_manager_role,
      'manager': can_delete_for_having_manager_role,
      'creator': can_delete_for_player,
      'guest': can_delete_for_player,
    }
    key, user = get_users
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
    assert queryset.count() == expected_count

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
  def test_get_access_to_detailpage(self, get_genres, get_users, client, is_owner, is_assigned, is_enabled):
    can_access = (is_owner or is_assigned) and is_enabled
    expected_type = {
      'superuser': status.HTTP_403_FORBIDDEN,
      'manager': status.HTTP_403_FORBIDDEN,
      'creator': status.HTTP_200_OK if can_access else status.HTTP_403_FORBIDDEN,
      'guest': status.HTTP_200_OK if can_access else status.HTTP_403_FORBIDDEN,
    }
    key, user = get_users
    genres = get_genres[:3]
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).order_by('pk')
    creators = factories.UserFactory.create_batch(5, is_active=True, role=RoleType.CREATOR)
    creators = UserModel.objects.filter(pk__in=self.pk_convertor(creators)).order_by('pk')
    guests = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.GUEST)
    members = (list(creators) + guests + [user]) if is_assigned and user.is_player() else (list(creators) + guests)
    members = UserModel.objects.filter(pk__in=self.pk_convertor(members)).order_by('pk')
    owner = user if is_owner and user.is_player() else factories.UserFactory(is_active=True, role=RoleType.GUEST)
    for creator in creators:
      for genre in genres:
        _ = factories.QuizFactory(creator=creator, genre=genre, is_completed=True)
    instance = factories.QuizRoomFactory(
      owner=owner,
      genres=list(genres),
      creators=list(creators),
      members=list(members),
      is_enabled=is_enabled,
    )
    instance.reset()
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

# ===================
# = UploadGenreView =
# ===================
@pytest.mark.quiz
@pytest.mark.view
@pytest.mark.django_db
class TestUploadGenreView(Common):
  form_view_url = reverse('quiz:upload_genre')

  def test_check_get_access(self, get_users, client):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_403_FORBIDDEN,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_users
    client.force_login(user)
    response = client.get(self.form_view_url)

    assert response.status_code == exact_types[key]

  @pytest.fixture(params=[
    'utf-8-with-header',
    'utf-8-without-header',
    'sjis-with-header',
    'sjis-without-header',
    'cp932-with-header',
    'cp932-without-header',
  ])
  def get_valid_form_param(self, request, get_manager):
    config = {
      'utf-8-with-header':    ('utf-8', True),
      'utf-8-without-header': ('utf-8', False),
      'sjis-with-header':     ('shift_jis', True),
      'sjis-without-header':  ('shift_jis', False),
      'cp932-with-header':    ('cp932', True),
      'cp932-without-header': ('cp932', False),
    }
    user = get_manager
    encoding, header = config[request.param]
    # Set genre
    valid_data = [
      'test-genre-0x0101',
      'test-genre-0x0221',
      'test-genre-0x0341',
    ]
    csv_file = SimpleUploadedFile('hoge.csv', bytes('foo,bar\n', encoding=encoding))
    # Create form data
    params = {
      'encoding': encoding,
      'csv_file': csv_file,
      'header': header,
    }

    yield user, params, valid_data

    # Post-process
    csv_file.close()

  @pytest.mark.parametrize([
    'data_indices',
  ], [
    ([0, 2, 1], ),
    ([0, 2, 1, 0, 1], ),
  ], ids=[
    'unique-list',
    'duplication-list',
  ])
  def test_check_valid_post_access(self, mocker, get_valid_form_param, client, data_indices):
    user, params, valid_data = get_valid_form_param
    records = [(valid_data[idx], ) for idx in data_indices]
    mock_csv_validator = mocker.patch('quiz.forms.validators.CustomCSVFileValidator.validate', return_value=None)
    mock_get_record_method = mocker.patch('quiz.forms.validators.CustomCSVFileValidator.get_record', return_value=records)
    # Send request
    client.force_login(user)
    response = client.post(self.form_view_url, data=params)
    # Collect expected queryset
    queryset = models.Genre.objects.filter(name__contains='test-genre-0x')

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == reverse('quiz:genre_list')
    assert all([queryset.filter(name=name).exists() for name in valid_data])
    assert mock_csv_validator.call_count == 1
    assert mock_get_record_method.call_count == 1

  @pytest.fixture(params=['form-invalid', 'invalid-bulk-create'])
  def get_invalid_form_param(self, mocker, request):
    input_header = True
    err_msg = ''

    if request.param == 'form-invalid':
      mocker.patch('quiz.forms.GenreUploadForm.clean', side_effect=ValidationError('invalid-inputs'))
      err_msg = 'invalid-inputs'
    elif request.param == 'invalid-bulk-create':
      from django.db.utils import IntegrityError
      mocker.patch('quiz.forms.GenreUploadForm.clean', return_value=None)
      mocker.patch('quiz.forms.validators.CustomCSVFileValidator.get_record', return_value=[])
      mocker.patch('quiz.models.Genre.objects.bulk_create', side_effect=IntegrityError('test'))
      err_msg = 'Include invalid records. Please check the detail: test.'
    # Setup temporary file
    encoding = 'utf-8'
    tmp_fp = tempfile.NamedTemporaryFile(mode='r+', encoding=encoding, suffix='.csv')
    with open(tmp_fp.name, encoding=encoding, mode='w') as csv_file:
      csv_file.write('Genre\ng1-pk\ng2-pk\n')
    with open(tmp_fp.name, encoding=encoding, mode='r') as fin:
      csv_file = SimpleUploadedFile(fin.name, bytes(fin.read(), encoding=fin.encoding))
      # Create form data
      params = {
        'encoding': encoding,
        'csv_file': csv_file,
        'header': input_header,
      }

    yield params, err_msg

    # Post-process
    csv_file.close()
    tmp_fp.close()

  def test_check_invalid_post_access(self, get_manager, get_invalid_form_param, client):
    user = get_manager
    params, err_msg = get_invalid_form_param
    # Send request
    client.force_login(user)
    response = client.post(self.form_view_url, data=params)
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(errors)

# =====================
# = DownloadGenreView =
# =====================
@pytest.mark.quiz
@pytest.mark.view
@pytest.mark.django_db
class TestDownloadGenreView(Common):
  form_view_url = reverse('quiz:download_genre')

  def test_check_get_access(self, get_users, client):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_200_OK,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_users
    client.force_login(user)
    response = client.get(self.form_view_url)

    assert response.status_code == exact_types[key]

  def test_check_post_access(self, mocker, get_has_creator_role_users, client):
    output = {
      'rows': (row for row in [['hoge'], ['foo']]),
      'header': ['Name'],
      'filename': 'genre-test1.csv',
    }
    mocker.patch('quiz.forms.GenreDownloadForm.create_response_kwargs', return_value=output)
    _, user = get_has_creator_role_users
    params = {
      'filename': 'dummy-name',
    }
    expected = bytes('Name\nhoge\nfoo\n', 'utf-8')
    # Post access
    client.force_login(user)
    response = client.post(self.form_view_url, data=params)
    cookie = response.cookies.get('genre_download_status')
    attachment = response.get('content-disposition')
    stream = response.getvalue()

    assert response.has_header('content-disposition')
    assert output['filename'] == urllib.parse.unquote(attachment.split('=')[1].replace('"', ''))
    assert cookie.value == 'completed'
    assert expected in stream

  @pytest.mark.parametrize([
    'params',
    'err_msg',
  ], [
    ({}, 'This field is required'),
    ({'filename': '1'*129}, 'Ensure this value has at most 128 character'),
  ], ids=[
    'is-empty',
    'too-long-filename',
  ])
  def test_invalid_post_request(self, get_has_creator_role_users, client, params, err_msg):
    _, user = get_has_creator_role_users
    # Post access
    client.force_login(user)
    response = client.post(self.form_view_url, data=params)
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(errors)

# ==================
# = UploadQuizView =
# ==================
@pytest.mark.quiz
@pytest.mark.view
@pytest.mark.django_db
class TestUploadQuizView(Common):
  form_view_url = reverse('quiz:upload_quiz')

  def test_check_get_access(self, get_users, client):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_200_OK,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_users
    client.force_login(user)
    response = client.get(self.form_view_url)

    assert response.status_code == exact_types[key]

  @pytest.fixture(params=[
    'utf-8-with-header',
    'utf-8-without-header',
    'sjis-with-header',
    'sjis-without-header',
    'cp932-with-header',
    'cp932-without-header',
  ])
  def get_valid_form_param(self, request, get_genres, get_has_creator_role_users):
    genre = get_genres[0]
    creators = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.CREATOR)
    config = {
      'utf-8-with-header':    ('utf-8', True),
      'utf-8-without-header': ('utf-8', False),
      'sjis-with-header':     ('shift_jis', True),
      'sjis-without-header':  ('shift_jis', False),
      'cp932-with-header':    ('cp932', True),
      'cp932-without-header': ('cp932', False),
    }
    _, user = get_has_creator_role_users
    encoding, header = config[request.param]
    # Set creator's members
    if user.has_manager_role():
      members = creators
      q_cond = Q(creator__pk__in=self.pk_convertor(creators), genre=genre)
    else:
      members = [user]
      q_cond = Q(creator=user, genre=genre)
    # Setup input data
    inputs = [
      ('uploaded-q1', 'uploaded-a1', True),
      ('uploaded-q2', 'uploaded-a2', False),
      ('uploaded-q3', 'uploaded-a3', False),
      ('uploaded-q4', 'uploaded-a4', True),
    ]
    # Set quiz
    valid_data = []
    for question, answer, is_completed in inputs:
      for creator in members:
        record = [str(creator.pk), genre.name, question, answer, is_completed]
        valid_data += [record]
    csv_file = SimpleUploadedFile('hoge.csv', bytes('foo,bar\n', encoding=encoding))
    # Create form data
    params = {
      'encoding': encoding,
      'csv_file': csv_file,
      'header': header,
    }

    yield user, params, q_cond, valid_data

    # Post-process
    csv_file.close()

  def test_check_valid_post_access(self, mocker, get_valid_form_param, client):
    user, params, q_cond, valid_data = get_valid_form_param
    mock_csv_validator = mocker.patch('quiz.forms.validators.CustomCSVFileValidator.validate', return_value=None)
    mock_get_record_method = mocker.patch('quiz.forms.validators.CustomCSVFileValidator.get_record', return_value=valid_data)
    # Send request
    client.force_login(user)
    response = client.post(self.form_view_url, data=params)
    # Collect expected queryset
    queryset = models.Quiz.objects.filter(q_cond)

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'] == reverse('quiz:quiz_list')
    assert all([
      queryset.filter(question=question, answer=answer, is_completed=is_completed).exists()
      for _, _, question, answer, is_completed in valid_data
    ])
    assert mock_csv_validator.call_count == 1
    assert mock_get_record_method.call_count == 1

  @pytest.fixture(params=['form-invalid', 'invalid-bulk-create', 'invalid-header-input'])
  def get_invalid_form_param(self, mocker, request):
    input_header = True
    err_msg = ''

    if request.param == 'form-invalid':
      mocker.patch('quiz.forms.QuizUploadForm.clean', side_effect=ValidationError('invalid-inputs'))
      err_msg = 'invalid-inputs'
    elif request.param == 'invalid-bulk-create':
      from django.db.utils import IntegrityError
      mocker.patch('quiz.forms.QuizUploadForm.clean', return_value=None)
      mocker.patch('quiz.forms.validators.CustomCSVFileValidator.get_record', return_value=[])
      mocker.patch('quiz.models.Quiz.objects.bulk_create', side_effect=IntegrityError('test'))
      err_msg = 'Include invalid records. Please check the detail: test.'
    elif request.param == 'invalid-header-input':
      input_header = False
      err_msg = 'The csv file includes invalid value(s).'
    # Setup temporary file
    encoding = 'utf-8'
    tmp_fp = tempfile.NamedTemporaryFile(mode='r+', encoding=encoding, suffix='.csv')
    with open(tmp_fp.name, encoding=encoding, mode='w') as csv_file:
      csv_file.write('Creator.pk,Genre,Question,Answer,IsCompleted\n')
      csv_file.write('c-pk,g-pk,q-1,a-1,True\n')
      csv_file.write('c-pk,g-pk,q-2,a-2,False\n')
    with open(tmp_fp.name, encoding=encoding, mode='r') as fin:
      csv_file = SimpleUploadedFile(fin.name, bytes(fin.read(), encoding=fin.encoding))
      # Create form data
      params = {
        'encoding': encoding,
        'csv_file': csv_file,
        'header': input_header,
      }

    yield params, err_msg

    # Post-process
    csv_file.close()
    tmp_fp.close()

  def test_check_invalid_post_access(self, get_has_creator_role_users, get_invalid_form_param, client):
    _, user = get_has_creator_role_users
    params, err_msg = get_invalid_form_param
    # Send request
    client.force_login(user)
    response = client.post(self.form_view_url, data=params)
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(errors)

# ====================
# = DownloadQuizView =
# ====================
@pytest.mark.quiz
@pytest.mark.view
@pytest.mark.django_db
class TestDownloadQuizView(Common):
  form_view_url = reverse('quiz:download_quiz')

  def test_check_get_access(self, get_users, client):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_200_OK,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_users
    client.force_login(user)
    response = client.get(self.form_view_url)

    assert response.status_code == exact_types[key]

  @pytest.fixture(params=['select-valid-quizzes', 'include-invalid-quizzes', 'no-quizzes'])
  def get_several_form_param(self, mocker, request, get_genres, get_has_creator_role_users):
    def generate_csv_data(instance):
      c_pk = str(instance.creator.pk)
      name = instance.genre.name
      qqq = instance.question
      ans = instance.answer
      is_c = instance.is_completed
      val = f'{c_pk},{name},{qqq},{ans},{is_c}'

      return val

    genres = get_genres[:3]
    _, user = get_has_creator_role_users
    _is_manager = user.has_manager_role()
    params = {
      'filename': 'hoge',
    }
    expected = {
      'filename': f'quiz-{params["filename"]}.csv',
    }
    creators = factories.UserFactory.create_batch(2, is_active=True, role=RoleType.CREATOR)
    target = user if not _is_manager else creators[0]
    # Create quizzes
    xs = [
      factories.QuizFactory(creator=target,      genre=genres[0], question='q-1', answer='a-5', is_completed=False), # 0
      factories.QuizFactory(creator=target,      genre=genres[1], question='q-2', answer='a-4', is_completed=True),  # 1
      factories.QuizFactory(creator=target,      genre=genres[2], question='q-3', answer='a-3', is_completed=False), # 2
      factories.QuizFactory(creator=creators[1], genre=genres[0], question='q-4', answer='a-2', is_completed=True),  # 3
      factories.QuizFactory(creator=creators[1], genre=genres[1], question='q-5', answer='a-1', is_completed=False), # 4
    ]
    all_queryset = models.Quiz.objects.filter(pk__in=self.pk_convertor(xs)).order_by('genre__name', 'creator__screen_name')
    mocker.patch('quiz.models.Quiz.objects.all', return_value=all_queryset)
    # Define each parameter
    inputs = [
      [xs[0], xs[1], xs[2]], # select-valid-quizzes
      [xs[0], xs[4], xs[2]], # include-invalid-quizzes (memo: order by `genre__name` so xs[0] (= genres[0]) -> xs[4] (= genres[1]) -> xs[2] (= genres[2]))
      [xs[0], xs[2]],        # for creator
    ]
    patterns = {
      'select-valid-quizzes': list(map(str, self.pk_convertor(inputs[0]))),
      'include-invalid-quizzes': list(map(str, self.pk_convertor(inputs[1]))),
      'no-quizzes': [],
    }
    header = ','.join(['Creator.pk', 'Genre', 'Question', 'Answer', 'IsCompleted']) + '\n'
    expected_vals = {
      'select-valid-quizzes': '\n'.join([generate_csv_data(item) for item in inputs[0]]) + '\n',
      'include-invalid-quizzes': '\n'.join([generate_csv_data(item) for item in (inputs[1] if _is_manager else inputs[2])]) + '\n',
      'no-quizzes': '',
    }
    # Collect relevant data
    key = request.param
    params['quizzes'] = patterns[key]
    expected['data'] = bytes(header + expected_vals[key], 'utf-8')

    return user, params, expected

  def test_check_post_access(self, get_several_form_param, client):
    user, params, expected = get_several_form_param
    # Post access
    client.force_login(user)
    response = client.post(self.form_view_url, data=params)
    cookie = response.cookies.get('quiz_download_status')
    attachment = response.get('content-disposition')
    stream = response.getvalue()

    assert response.has_header('content-disposition')
    assert expected['filename'] == urllib.parse.unquote(attachment.split('=')[1].replace('"', ''))
    assert cookie.value == 'completed'
    assert expected['data'] in stream

  @pytest.mark.parametrize([
    'params',
    'err_msg',
  ], [
    ({}, 'This field is required'),
    ({'filename': '1'*129}, 'Ensure this value has at most 128 character'),
  ], ids=[
    'is-empty',
    'too-long-filename',
  ])
  def test_invalid_post_request(self, get_has_creator_role_users, client, params, err_msg):
    _, user = get_has_creator_role_users
    # Post access
    client.force_login(user)
    response = client.post(self.form_view_url, data=params)
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(errors)

# ====================
# = QuizAjaxResponse =
# ====================
@pytest.mark.quiz
@pytest.mark.view
@pytest.mark.django_db
class TestQuizAjaxResponse(Common):
  ajax_url = reverse('quiz:ajax_get_quizzes')

  def test_check_get_access(self, get_users, client):
    exact_types = {
      'superuser': status.HTTP_200_OK,
      'manager': status.HTTP_200_OK,
      'creator': status.HTTP_200_OK,
      'guest': status.HTTP_403_FORBIDDEN,
    }
    key, user = get_users
    client.force_login(user)
    response = client.get(self.ajax_url)

    assert response.status_code == exact_types[key]

  def test_valid_get_request(self, mocker, get_genres, get_has_creator_role_users, client):
    genre = get_genres[0]
    creators = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.CREATOR)
    _, user = get_has_creator_role_users
    # Create quiz
    quizzes = [factories.QuizFactory(creator=creator, genre=genre, is_completed=True) for creator in creators]

    if not user.has_manager_role():
      additional_data = [
        factories.QuizFactory(creator=user, genre=genre, is_completed=True),
        factories.QuizFactory(creator=user, genre=genre, is_completed=False),
      ]
      quizzes += additional_data
      expected = list(map(str, self.pk_convertor(additional_data)))
    else:
      expected = list(map(str, self.pk_convertor(quizzes)))
    # Convert list to queryset
    quizzes = models.Quiz.objects.filter(pk__in=self.pk_convertor(quizzes)).order_by('pk')
    mocker.patch('quiz.models.Quiz.objects.select_related', return_value=quizzes)
    # Send GET request
    client.force_login(user)
    response = client.get(self.ajax_url)
    data = json.loads(response.content)
    estimated = data['quizzes']

    assert response.status_code == status.HTTP_200_OK
    assert all([item['pk'] in expected for item in estimated])

  @pytest.mark.parametrize([
    'is_authenticated',
    'status_code',
  ], [
    (True, status.HTTP_405_METHOD_NOT_ALLOWED),
    (False, status.HTTP_403_FORBIDDEN),
  ], ids=[
    'is-authenticated',
    'is-not-authenticated',
  ])
  def test_check_post_access(self, get_users, client, is_authenticated, status_code):
    key, user = get_users

    if is_authenticated:
      client.force_login(user)
      # Upate status code
      if key == 'guest':
        status_code = status.HTTP_403_FORBIDDEN
    response = client.post(self.ajax_url)

    assert response.status_code == status_code