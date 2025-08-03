import pytest
from webtest.app import AppError
from django.contrib.auth import get_user_model
from django.utils import timezone, dateformat
from django.urls import reverse
from django.db.models import Q
from app_tests import status, factories
from app_tests.integration_tests import get_current_path
from account.models import RoleType
from quiz import models
import urllib.parse

UserModel = get_user_model()

@pytest.fixture(scope='module')
def get_genres(django_db_blocker):
  with django_db_blocker.unblock():
    genres = []

    for idx in range(6):
      output = dateformat.format(timezone.now(), 'Ymd-His.u')
      name = f'quiz{idx}-{output}'

      try:
        instance = models.Genre.objects.get(name=name)
      except:
        instance = factories.GenreFactory(name=name, is_enabled=True)
      genres += [instance]

  return genres

@pytest.fixture(scope='module')
def create_quizzes(django_db_blocker, get_genres, get_creator):
  with django_db_blocker.unblock():
    instances = []
    genres = get_genres
    others = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.CREATOR)
    instances += [
      factories.QuizFactory(creator=others[0], genre=genres[0], is_completed=True),
      factories.QuizFactory(creator=others[1], genre=genres[1], is_completed=False),
      factories.QuizFactory(creator=others[2], genre=genres[0], is_completed=True),
    ]
    creator = get_creator
    instances += [
      factories.QuizFactory(creator=creator, genre=genres[0], is_completed=True),
      factories.QuizFactory(creator=creator, genre=genres[1], is_completed=False),
    ]
    all_queryset = models.Quiz.objects.filter(pk__in=[obj.pk for obj in instances])

  return creator, others[1], all_queryset

@pytest.fixture(scope='module')
def create_members(get_genres, django_db_blocker):
  with django_db_blocker.unblock():
    creators = list(factories.UserFactory.create_batch(4, is_active=True, role=RoleType.CREATOR))
    guests = list(factories.UserFactory.create_batch(3, is_active=True, role=RoleType.GUEST))
    genres = get_genres

  return creators, guests, genres

@pytest.fixture(params=['guest', 'creator'], scope='module')
def create_rooms(django_db_blocker, create_members, request):
  _convertor = lambda xs: [obj.pk for obj in xs]
  role = RoleType.GUEST if request.param == 'guest' else RoleType.CREATOR

  with django_db_blocker.unblock():
    creators, guests, genres = create_members
    members = creators + guests
    user = factories.UserFactory(is_active=True, role=role)
    configs = [
      ### Not relevant ###
      {'owner': creators[0], 'name': 'target-room', 'creators': [creators[1].pk, creators[2].pk], 'genres': [genres[0].pk, genres[3].pk], 'members': _convertor(guests), 'is_enabled': False},
      # The user includes members
      {'owner': creators[1], 'name': 'test-room1',  'creators': [creators[2].pk, creators[3].pk], 'members': _convertor(guests+[user]), 'is_enabled': True},
      ### Not relevant ###
      {'owner': guests[0],   'name': 'test-room2',  'creators': [creators[0].pk, creators[3].pk], 'genres': [genres[5].pk], 'members': _convertor(members), 'is_enabled': True},
      # The user includes members
      {'owner': guests[1],   'name': 'test-room3',  'genres':   [genres[3].pk, genres[4].pk], 'members': _convertor(members+[user]), 'is_enabled': False},
      # The user is an owner
      {'owner': user,        'name': 'target-room', 'creators': [creators[0].pk], 'members': _convertor(guests), 'is_enabled': True},
      # The user is an owner
      {'owner': user,        'name': 'test-room4',  'creators': [creators[1].pk], 'members': _convertor(creators), 'is_enabled': False},
    ]
    instances = [factories.QuizRoomFactory(max_question=10, **kwargs) for kwargs in configs]
    all_queryset = models.QuizRoom.objects.filter(pk__in=_convertor(instances))

  return user, guests[0], all_queryset

class Common:
  index_url = reverse('utils:index')
  pk_convertor = lambda _self, xs: [item.pk for item in xs]
  compare_qs = lambda _self, qs, exacts: all([val.pk == ex.pk for val, ex in zip(qs, exacts)])

# =========
# = Genre =
# =========
@pytest.mark.webtest
@pytest.mark.django_db
class TestGenre(Common):
  genre_list_url = reverse('quiz:genre_list')
  create_genre_url = reverse('quiz:create_genre')
  update_genre_url = lambda _self, pk: reverse('quiz:update_genre', kwargs={'pk': pk})

  def test_can_move_to_genre_page(self, csrf_exempt_django_app, get_has_manager_role_user):
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    page = app.get(self.index_url, user=user)
    response = page.click('Quiz genre')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.genre_list_url

  def test_cannot_move_to_genre_page(self, csrf_exempt_django_app, get_players):
    _, user = get_players
    app = csrf_exempt_django_app
    page = app.get(self.index_url, user=user)

    with pytest.raises(IndexError):
      _ = page.click('Quiz genre')

  def test_can_move_to_genre_create_page(self, csrf_exempt_django_app, get_has_manager_role_user):
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    page = app.get(self.genre_list_url, user=user)
    response = page.click('Create a new genre')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.create_genre_url

  def test_can_move_to_parent_page_from_genre_create_page(self, csrf_exempt_django_app, get_has_manager_role_user):
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    page = app.get(self.create_genre_url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.genre_list_url

  @pytest.mark.parametrize([
    'config',
    'is_enabled',
  ], [
    ({'name': 'hoge-quiz-integration', 'is_enabled': True}, True),
    ({'name': 'hoge-quiz-integration', 'is_enabled': False}, False),
    ({'name': 'hoge-quiz-integration'}, True),
  ], ids=[
    'is-enable',
    'is-not-enable',
    'not-set',
  ])
  def test_send_post_request(self, csrf_exempt_django_app, get_has_manager_role_user, config, is_enabled):
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    forms = app.get(self.create_genre_url, user=user).forms
    form = forms['genre-form']
    for key, val in config.items():
      form[key] = val
    response = form.submit().follow()
    instance = models.Genre.objects.get(name=config['name'])

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.genre_list_url
    assert instance.is_enabled == is_enabled

  def test_can_move_to_genre_update_page(self, csrf_exempt_django_app, get_genres, get_has_manager_role_user):
    instance = get_genres[0]
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    page = app.get(self.genre_list_url, user=user)
    genres = page.context['genres']
    # Set output url
    if len(genres) > 0:
      instance = genres[0]
    output_url = self.update_genre_url(instance.pk)
    response = page.click('Edit', href=output_url)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == output_url

  def test_can_move_to_parent_page_from_genre_update_page(self, csrf_exempt_django_app, get_genres, get_has_manager_role_user):
    instance = get_genres[0]
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    url = self.update_genre_url(instance.pk)
    page = app.get(url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.genre_list_url

  def test_update_genre(self, csrf_exempt_django_app, get_has_manager_role_user):
    instance = factories.GenreFactory(is_enabled=False)
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    url = self.update_genre_url(instance.pk)
    forms = app.get(url, user=user).forms
    form = forms['genre-form']
    name = 'updated-hoge-integration'
    form['name'] = name
    form['is_enabled'] = True
    response = form.submit().follow()
    instance = models.Genre.objects.get(name=name)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.genre_list_url
    assert instance.name == name
    assert instance.is_enabled

# ========
# = Quiz =
# ========
@pytest.mark.webtest
@pytest.mark.django_db
class TestQuiz(Common):
  quiz_list_url = reverse('quiz:quiz_list')
  create_quiz_url = reverse('quiz:create_quiz')
  update_quiz_url = lambda _self, pk: reverse('quiz:update_quiz', kwargs={'pk': pk})
  delete_quiz_url = lambda _self, pk: reverse('quiz:delete_quiz', kwargs={'pk': pk})

  def test_can_move_to_quiz_page(self, csrf_exempt_django_app, get_editors):
    _, user = get_editors
    app = csrf_exempt_django_app
    page = app.get(self.index_url, user=user)
    response = page.click('Check/Create/Update/Delete quizzes')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url

  def test_cannot_move_to_quiz_page(self, csrf_exempt_django_app, get_guest):
    user = get_guest
    app = csrf_exempt_django_app
    page = app.get(self.index_url, user=user)

    with pytest.raises(IndexError):
      _ = page.click('Check/Create/Update/Delete quizzes')

  def test_can_move_to_quiz_create_page(self, csrf_exempt_django_app, get_creator):
    user = get_creator
    app = csrf_exempt_django_app
    page = app.get(self.quiz_list_url, user=user)
    response = page.click('Create a new quiz')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.create_quiz_url

  def test_can_move_to_parent_page_from_quiz_create_page(self, csrf_exempt_django_app, get_creator):
    user = get_creator
    app = csrf_exempt_django_app
    page = app.get(self.create_quiz_url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url

  def test_cannot_move_to_quiz_create_page(self, csrf_exempt_django_app, get_has_manager_role_user):
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    page = app.get(self.quiz_list_url, user=user)

    with pytest.raises(IndexError):
      _ = page.click('Create a new quiz')

  def test_check_quiz_queryset_for_manager(self, csrf_exempt_django_app, mocker, create_quizzes, get_has_manager_role_user):
    creator, _, all_queryset = create_quizzes
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    mocker.patch('quiz.views.QuizListPage.get_queryset', return_value=all_queryset)
    response = app.get(self.quiz_list_url, user=user)
    quizzes = response.context['quizzes']
    estimated = models.Quiz.objects.filter(pk__in=[_quiz.pk for _quiz in quizzes])
    ids = all_queryset.values_list('pk', flat=True)

    assert response.status_code == status.HTTP_200_OK
    assert estimated.count() == len(ids)
    assert all([_quiz.pk in ids for _quiz in estimated])

  def test_check_quiz_queryset_for_creator(self, csrf_exempt_django_app, create_quizzes):
    user, _, all_queryset = create_quizzes
    app = csrf_exempt_django_app
    response = app.get(self.quiz_list_url, user=user)
    quizzes = response.context['quizzes']
    estimated = all_queryset.filter(pk__in=[_quiz.pk for _quiz in quizzes]).order_by('pk')
    expected = all_queryset.filter(creator=user).order_by('pk')

    assert response.status_code == status.HTTP_200_OK
    assert estimated.count() == expected.count()
    assert self.compare_qs(estimated, expected)

  def test_check_filtering_method_for_manager(self, csrf_exempt_django_app, mocker, get_genres, create_quizzes, get_has_manager_role_user):
    genres = get_genres
    creator, _, all_queryset = create_quizzes
    _, user = get_has_manager_role_user
    mocker.patch('quiz.views.QuizListPage.get_queryset', return_value=all_queryset)
    app = csrf_exempt_django_app
    forms = app.get(self.quiz_list_url, user=user).forms
    form = forms['quiz-search-form']
    form['genres'] = [str(genres[0].pk)]
    form['creators'] = [str(creator.pk)]
    form['is_and_op'] = False
    response = form.submit()
    quizzes = response.context['quizzes']
    estimated = models.Quiz.objects.filter(pk__in=[_quiz.pk for _quiz in quizzes]).order_by('pk')
    expected = all_queryset.filter(Q(genre__pk__in=[genres[0].pk]) | Q(creator__pk__in=[creator.pk])).order_by('pk')

    assert response.status_code == status.HTTP_200_OK
    assert estimated.count() == expected.count()
    assert self.compare_qs(estimated, expected)

  def test_check_filtering_method_for_creator(self, csrf_exempt_django_app, get_genres, create_quizzes):
    genres = get_genres
    user, _, all_queryset = create_quizzes
    app = csrf_exempt_django_app
    forms = app.get(self.quiz_list_url, user=user).forms
    form = forms['quiz-search-form']
    form['genres'] = [str(genres[0].pk)]
    form['creators'] = [str(user.pk)]
    form['is_and_op'] = False
    response = form.submit()
    quizzes = response.context['quizzes']
    estimated = models.Quiz.objects.filter(pk__in=[_quiz.pk for _quiz in quizzes]).order_by('pk')
    expected = all_queryset.filter(creator=user).order_by('pk')

    assert response.status_code == status.HTTP_200_OK
    assert estimated.count() == expected.count()
    assert self.compare_qs(estimated, expected)

  def test_send_create_request(self, csrf_exempt_django_app, get_genres, get_creator):
    user = get_creator
    app = csrf_exempt_django_app
    genre = get_genres[3]
    forms = app.get(self.create_quiz_url, user=user).forms
    form = forms['quiz-form']
    form['genre'] = str(genre.pk)
    form['question'] = 'hogehoge'
    form['answer'] = 'fugafuga'
    form['is_completed'] = False
    response = form.submit().follow()
    all_counts = models.Quiz.objects.filter(creator=user, genre=genre).count()

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url
    assert all_counts == 1

  def test_invalid_create_request(self, csrf_exempt_django_app, get_genres, get_creator):
    user = get_creator
    app = csrf_exempt_django_app
    genre = get_genres[0]
    invalid_genre = factories.GenreFactory(is_enabled=False)
    forms = app.get(self.create_quiz_url, user=user).forms
    form = forms['quiz-form']

    with pytest.raises(ValueError):
      form['genre'] = str(invalid_genre.pk)

  def test_can_move_to_quiz_update_page(self, csrf_exempt_django_app, get_has_manager_role_user):
    instance = factories.QuizFactory()
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    page = app.get(self.quiz_list_url, user=user)
    quizzes = page.context['quizzes']
    # Set output url
    if len(quizzes) > 0:
      instance = quizzes[0]
    output_url = self.update_quiz_url(instance.pk)
    response = page.click('Edit', href=output_url)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == output_url

  def test_can_move_to_parent_page_from_quiz_update_page(self, csrf_exempt_django_app, get_has_manager_role_user):
    instance = factories.QuizFactory()
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    url = self.update_quiz_url(instance.pk)
    page = app.get(url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url

  def test_cannot_move_to_other_creators_update_page(self, csrf_exempt_django_app, create_quizzes):
    user, other, _ = create_quizzes
    instance = other.quizzes.first()
    app = csrf_exempt_django_app
    url = self.update_quiz_url(instance.pk)

    with pytest.raises(AppError) as ex:
      _ = app.get(url, user=user)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  def test_update_quiz_for_creator(self, csrf_exempt_django_app, create_quizzes):
    user, _, _ = create_quizzes
    instance = user.quizzes.first()
    app = csrf_exempt_django_app
    url = self.update_quiz_url(instance.pk)
    forms = app.get(url, user=user).forms
    form = forms['quiz-form']
    question = 'updated-hoge-question'
    answer = 'update-hoge-answer'
    form['question'] = question
    form['answer'] = answer
    form['is_completed'] = False
    response = form.submit().follow()
    instance = models.Quiz.objects.get(pk=instance.pk)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url
    assert instance.question == question
    assert instance.answer == answer
    assert not instance.is_completed

  def test_update_quiz_for_manager(self, csrf_exempt_django_app, create_quizzes, get_has_manager_role_user):
    _, other, _ = create_quizzes
    _, user = get_has_manager_role_user
    instance = other.quizzes.first()
    app = csrf_exempt_django_app
    url = self.update_quiz_url(instance.pk)
    forms = app.get(url, user=user).forms
    form = forms['quiz-form']
    question = f'updated-{other}-question'
    answer = f'update-{other}-answer'
    form['question'] = question
    form['answer'] = answer
    form['is_completed'] = True
    response = form.submit().follow()
    instance = models.Quiz.objects.get(pk=instance.pk)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url
    assert instance.question == question
    assert instance.answer == answer
    assert instance.is_completed

  def test_cannot_access_to_delete_page(self, csrf_exempt_django_app, create_quizzes, get_users):
    creator, _, _ = create_quizzes
    _, user = get_users
    instance = creator.quizzes.first()
    app = csrf_exempt_django_app
    url = self.delete_quiz_url(instance.pk)

    with pytest.raises(AppError) as ex:
      _ = app.get(url, user=user)

    assert any([
      str(status.HTTP_403_FORBIDDEN) in ex.value.args[0],
      str(status.HTTP_405_METHOD_NOT_ALLOWED) in ex.value.args[0],
    ])

  def test_delete_quiz_for_manager(self, csrf_exempt_django_app, create_quizzes, get_has_manager_role_user):
    _, other, _ = create_quizzes
    _, user = get_has_manager_role_user
    instance = other.quizzes.first()
    app = csrf_exempt_django_app
    url = self.delete_quiz_url(instance.pk)
    response = app.post(url, user=user).follow()
    queryset = models.Quiz.objects.filter(pk__in=[instance.pk])

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url
    assert queryset.count() == 0

  def test_delete_quiz_for_creator(self, csrf_exempt_django_app, create_quizzes):
    user, _, _ = create_quizzes
    instance = user.quizzes.first()
    app = csrf_exempt_django_app
    url = self.delete_quiz_url(instance.pk)
    response = app.post(url, user=user).follow()
    queryset = models.Quiz.objects.filter(pk__in=[instance.pk])

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url
    assert queryset.count() == 0

  def test_delete_quiz_for_other_creator(self, csrf_exempt_django_app, create_quizzes):
    user, other, _ = create_quizzes
    instance = other.quizzes.first()
    app = csrf_exempt_django_app
    url = self.delete_quiz_url(instance.pk)

    with pytest.raises(AppError) as ex:
      _ = app.post(url, user=user)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

# ============
# = QuizRoom =
# ============
@pytest.mark.webtest
@pytest.mark.django_db
class TestQuizRoom(Common):
  room_list_url = reverse('quiz:room_list')
  create_room_url = reverse('quiz:create_room')
  update_room_url = lambda _self, pk: reverse('quiz:update_room', kwargs={'pk': pk})
  delete_room_url = lambda _self, pk: reverse('quiz:delete_room', kwargs={'pk': pk})
  enter_room_url = lambda _self, pk: reverse('quiz:enter_room', kwargs={'pk': pk})
  pk_str_convertor = lambda _self, xs: [str(item.pk) for item in xs]

  def test_can_move_to_room_page(self, csrf_exempt_django_app, get_users):
    _, user = get_users
    app = csrf_exempt_django_app
    page = app.get(self.index_url, user=user)
    response = page.click('Quiz room')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.room_list_url

  def test_can_move_to_room_create_page(self, csrf_exempt_django_app, get_players):
    _, user = get_players
    app = csrf_exempt_django_app
    page = app.get(self.room_list_url, user=user)
    response = page.click('Create a new quiz room')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.create_room_url

  def test_can_move_to_parent_page_from_room_create_page(self, csrf_exempt_django_app, get_players):
    _, user = get_players
    app = csrf_exempt_django_app
    page = app.get(self.create_room_url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.room_list_url

  def test_cannot_move_to_room_create_page(self, csrf_exempt_django_app, get_has_manager_role_user):
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    page = app.get(self.room_list_url, user=user)

    with pytest.raises(IndexError):
      _ = page.click('Create a new quiz room')

  def test_check_room_queryset_for_manager(self, csrf_exempt_django_app, mocker, create_rooms, get_has_manager_role_user):
    _, user = get_has_manager_role_user
    _, _, all_queryset = create_rooms
    app = csrf_exempt_django_app
    mocker.patch('quiz.models.QuizRoom.objects.collect_relevant_rooms', return_value=all_queryset)
    # Send GET request
    response = app.get(self.room_list_url, user=user)
    rooms = models.QuizRoom.objects.filter(pk__in=[_room.pk for _room in response.context['rooms']]).order_by('pk')
    expected = all_queryset.order_by('pk')

    assert response.status_code == status.HTTP_200_OK
    assert rooms.count() == expected.count()
    assert self.compare_qs(rooms, expected)

  def test_check_room_queryset_for_player(self, csrf_exempt_django_app, mocker, create_rooms):
    user, _, all_queryset = create_rooms
    app = csrf_exempt_django_app
    # Mock for related_name's elements
    mock_user = mocker.patch('account.models.User', side_effect=UserModel())
    mock_user.quiz_rooms.all.return_value = all_queryset.filter(owner=user)
    mock_user.assigned_rooms.all.return_value = all_queryset.filter(members__pk__in=[user.pk])
    response = app.get(self.room_list_url, user=user)
    rooms = models.QuizRoom.objects.filter(pk__in=[_room.pk for _room in response.context['rooms']]).order_by('pk')
    expected = all_queryset.filter(Q(owner=user) | Q(members__pk__in=[user.pk], is_enabled=True)).order_by('pk').distinct()

    assert response.status_code == status.HTTP_200_OK
    assert rooms.count() == expected.count()
    assert self.compare_qs(rooms, expected)

  @pytest.mark.parametrize([
    'name',
    'pair',
  ], [
    ('target-room', {True: 1, False: 2}),
    ('test-room', {True: 2, False: 4}),
    ('room', {True: 3, False: 6}),
  ], ids=[
    'target-room-and-manager-2-player-1',
    'test-room-and-manager-4-player-2',
    'room-and-manager-6-player-3',
  ])
  def test_check_filtering_method(self, csrf_exempt_django_app, mocker, create_rooms, get_users, name, pair):
    _, _u_tmp = get_users
    is_player = _u_tmp.is_player()
    owner, _, all_queryset = create_rooms
    expected_count = pair[is_player]
    app = csrf_exempt_django_app
    # Define queryset
    if is_player:
      user = owner
      _user_qs = all_queryset.filter(Q(owner=user) | Q(members__in=[user], is_enabled=True))
    else:
      user = _u_tmp
      _user_qs = all_queryset
    mocker.patch('quiz.models.QuizRoom.objects.collect_relevant_rooms', return_value=_user_qs)
    # Collect Form data
    forms = app.get(self.room_list_url, user=user).forms
    form = forms['room-search-form']
    form['name'] = name
    response = form.submit()
    rooms = models.QuizRoom.objects.filter(pk__in=[_room.pk for _room in response.context['rooms']]).order_by('pk')

    if is_player:
      expected = all_queryset.filter(Q(owner=user, name__contains=name) | Q(members__pk__in=[user.pk], is_enabled=True, name__contains=name)).order_by('pk').distinct()
    else:
      expected = all_queryset.filter(name__contains=name).order_by('pk')

    assert response.status_code == status.HTTP_200_OK
    assert rooms.count() == expected.count() == expected_count
    assert self.compare_qs(rooms, expected)

  def test_send_create_request(self, csrf_exempt_django_app, create_members, get_players):
    _, user = get_players
    app = csrf_exempt_django_app
    creators, guests, genres = create_members
    # Update user's friends
    user.friends.add(*guests)
    user.save()
    _ = factories.QuizFactory(creator=creators[0], genre=genres[0], is_completed=True)
    _ = factories.QuizFactory(creator=creators[1], genre=genres[0], is_completed=True)
    forms = app.get(self.create_room_url, user=user).forms
    form = forms['room-form']
    creator_ids = self.pk_str_convertor([creators[0], creators[1]])
    genre_ids = self.pk_str_convertor([genres[0]])
    member_ids = self.pk_str_convertor([guests[0], guests[1]])
    form['name'] = 'test-room'
    form['creators'] = creator_ids
    form['genres'] = genre_ids
    form['members'] = member_ids
    form['max_question'] = 2
    form['is_enabled'] = False
    response = form.submit().follow()
    instance = models.QuizRoom.objects.get(owner=user, max_question=2)
    # Rollback user's friends
    user.friends.clear()
    user.save()

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.room_list_url
    assert all([pk in creator_ids for pk in self.pk_str_convertor(instance.creators.all())])
    assert all([pk in genre_ids for pk in self.pk_str_convertor(instance.genres.all())])
    assert all([pk in member_ids for pk in self.pk_str_convertor(instance.members.all())])
    assert not instance.is_enabled

  def test_invalid_create_request(self, csrf_exempt_django_app, create_members, get_players):
    _, user = get_players
    app = csrf_exempt_django_app
    _, guests, _ = create_members
    # Update user's friends
    user.friends.add(*guests)
    user.save()
    forms = app.get(self.create_room_url, user=user).forms
    form = forms['room-form']
    form['name'] = 'test-room'
    form['members'] = self.pk_str_convertor([guests[0], guests[1]])
    form['max_question'] = 1
    form['is_enabled'] = True
    response = form.submit()
    errors = response.context['form'].errors
    # Rollback user's friends
    user.friends.clear()
    user.save()

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.create_room_url
    assert 'You have to assign at least one of genres or creators to the quiz room.' in str(errors)

  def test_can_move_to_room_update_page(self, csrf_exempt_django_app, create_members, get_has_manager_role_user):
    creators, guests, genres = create_members
    _ = factories.QuizRoomFactory(
      owner=creators[0],
      genres=[genres[1].pk, genres[2].pk],
      members=[guests[0].pk],
    )
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    page = app.get(self.room_list_url, user=user)
    rooms = page.context['rooms']
    output_url = self.update_room_url(rooms[0].pk)
    response = page.click('Edit', href=output_url)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == output_url

  def test_can_move_to_parent_page_from_room_update_page(self, csrf_exempt_django_app, create_members, get_has_manager_role_user):
    creators, guests, genres = create_members
    instance = factories.QuizRoomFactory(
      owner=creators[0],
      genres=[genres[1].pk, genres[2].pk],
      members=[guests[0].pk],
    )
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    url = self.update_room_url(instance.pk)
    page = app.get(url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.room_list_url

  def test_cannot_move_to_other_creators_update_page(self, csrf_exempt_django_app, create_rooms):
    user, other, _ = create_rooms
    instance = other.quiz_rooms.first()
    app = csrf_exempt_django_app
    url = self.update_room_url(instance.pk)

    with pytest.raises(AppError) as ex:
      _ = app.get(url, user=user)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  @pytest.fixture
  def get_being_able_to_modify_rooms(self, django_db_blocker, get_players, get_genres):
    with django_db_blocker.unblock():
      creators = list(factories.UserFactory.create_batch(4, is_active=True, role=RoleType.CREATOR))
      guests = list(factories.UserFactory.create_batch(3, is_active=True, role=RoleType.GUEST))
      genres = get_genres
      members = creators + guests
      _, user = get_players
      configs = [
        ### Not relevant ###
        {'owner': creators[0], 'creators': [creators[1].pk, creators[2].pk], 'genres': [genres[0].pk, genres[3].pk], 'members': self.pk_convertor(guests), 'is_enabled': False},
        # The user includes members
        {'owner': creators[1], 'creators': [creators[2].pk, creators[3].pk], 'members': self.pk_convertor(guests+[user]), 'is_enabled': True},
        # The user is an owner
        {'owner': user, 'creators': [creators[0].pk], 'members': self.pk_convertor(guests), 'is_enabled': True},
        # The user is an owner
        {'owner': user, 'creators': [creators[1].pk], 'members': self.pk_convertor(creators), 'is_enabled': False},
      ]
      _ = factories.QuizFactory(creator=creators[0], genre=genres[0], is_completed=True)
      _ = factories.QuizFactory(creator=creators[0], genre=genres[1], is_completed=True)
      _ = factories.QuizFactory(creator=creators[1], genre=genres[0], is_completed=True)
      _ = factories.QuizFactory(creator=creators[1], genre=genres[1], is_completed=True)
      if user.is_creator():
        _ = factories.QuizFactory(creator=user, genre=genres[0], is_completed=True)
        _ = factories.QuizFactory(creator=user, genre=genres[1], is_completed=True)
      for kwargs in configs:
        _ = factories.QuizRoomFactory(max_question=2, **kwargs)

    return user, creators[0]

  def test_update_room_for_creator(self, csrf_exempt_django_app, create_members, get_being_able_to_modify_rooms):
    creators, guests, genres = create_members
    user, _ = get_being_able_to_modify_rooms
    _ = factories.QuizFactory(creator=creators[0], genre=genres[0], is_completed=True)
    _ = factories.QuizFactory(creator=creators[2], genre=genres[0], is_completed=True)
    target = user.quiz_rooms.first()
    app = csrf_exempt_django_app
    url = self.update_room_url(target.pk)
    forms = app.get(url, user=user).forms
    form = forms['room-form']
    creator_ids = self.pk_str_convertor([creators[0], creators[2]])
    form['creators'] = creator_ids
    form['max_question'] = 2
    form['is_enabled'] = True
    response = form.submit().follow()
    instance = models.QuizRoom.objects.get(pk=target.pk)
    genres_ids = self.pk_str_convertor(target.genres.all())
    members_ids = self.pk_str_convertor(target.members.all())

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.room_list_url
    assert all([pk in creator_ids for pk in self.pk_str_convertor(instance.creators.all())])
    assert all([pk in genres_ids for pk in self.pk_str_convertor(instance.genres.all())])
    assert all([pk in members_ids for pk in self.pk_str_convertor(instance.members.all())])
    assert instance.max_question == 2
    assert instance.is_enabled

  def test_update_room_for_manager(self, csrf_exempt_django_app, create_members, get_being_able_to_modify_rooms, get_has_manager_role_user):
    creators, guests, genres = create_members
    _, other = get_being_able_to_modify_rooms
    _ = factories.QuizFactory(creator=creators[0], genre=genres[0], is_completed=True)
    _ = factories.QuizFactory(creator=creators[2], genre=genres[0], is_completed=True)
    _, user = get_has_manager_role_user
    target = other.quiz_rooms.first()
    app = csrf_exempt_django_app
    url = self.update_room_url(target.pk)
    forms = app.get(url, user=user).forms
    form = forms['room-form']
    creator_ids = self.pk_str_convertor([creators[0], creators[2]])
    form['creators'] = creator_ids
    form['max_question'] = 2
    form['is_enabled'] = True
    response = form.submit().follow()
    instance = models.QuizRoom.objects.get(pk=target.pk)
    genres_ids = self.pk_str_convertor(target.genres.all())
    members_ids = self.pk_str_convertor(target.members.all())

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.room_list_url
    assert all([pk in creator_ids for pk in self.pk_str_convertor(instance.creators.all())])
    assert all([pk in genres_ids for pk in self.pk_str_convertor(instance.genres.all())])
    assert all([pk in members_ids for pk in self.pk_str_convertor(instance.members.all())])
    assert instance.max_question == 2
    assert instance.is_enabled

  def test_cannot_access_to_delete_page(self, csrf_exempt_django_app, get_being_able_to_modify_rooms, get_users):
    creator, _ = get_being_able_to_modify_rooms
    _, user = get_users
    instance = creator.quiz_rooms.first()
    app = csrf_exempt_django_app
    url = self.delete_room_url(instance.pk)

    with pytest.raises(AppError) as ex:
      _ = app.get(url, user=user)

    assert any([
      str(status.HTTP_403_FORBIDDEN) in ex.value.args[0],
      str(status.HTTP_405_METHOD_NOT_ALLOWED) in ex.value.args[0],
    ])

  def test_can_delete_room_for_manager(self, csrf_exempt_django_app, create_members, get_has_manager_role_user):
    creators, guests, genres = create_members
    instance = factories.QuizRoomFactory(
      owner=guests[0],
      creators=[creators[0], creators[1]],
      members=[guests[1], creators[1]],
      is_enabled=False,
    )
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    url = self.delete_room_url(instance.pk)
    response = app.post(url, user=user).follow()
    queryset = models.QuizRoom.objects.filter(pk__in=[instance.pk])

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.room_list_url
    assert queryset.count() == 0

  def test_can_delete_room_for_player(self, csrf_exempt_django_app, create_members, get_players):
    _, user = get_players
    creators, guests, genres = create_members
    instance = factories.QuizRoomFactory(
      owner=user,
      creators=[creators[0], creators[1]],
      members=[guests[1], creators[1]],
      is_enabled=False,
    )
    app = csrf_exempt_django_app
    url = self.delete_room_url(instance.pk)
    response = app.post(url, user=user).follow()
    queryset = models.QuizRoom.objects.filter(pk__in=[instance.pk])

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.room_list_url
    assert queryset.count() == 0

  def test_cannot_delete_room_for_player(self, csrf_exempt_django_app, create_members, get_users):
    _, user = get_users
    creators, guests, genres = create_members
    owner = user if user.is_player() else creators[0]
    instance = factories.QuizRoomFactory(
      owner=owner,
      creators=[creators[0], creators[1]],
      members=[guests[1], creators[1]],
      is_enabled=True,
    )
    app = csrf_exempt_django_app
    url = self.delete_room_url(instance.pk)

    with pytest.raises(AppError) as ex:
      _ = app.post(url, user=user)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  def test_cannot_delete_room_for_other_creator(self, csrf_exempt_django_app, create_members, get_players):
    _, user = get_players
    creators, guests, genres = create_members
    instance = factories.QuizRoomFactory(
      owner=creators[0],
      creators=[creators[0], creators[1]],
      members=[guests[1], creators[1]],
      is_enabled=False,
    )
    app = csrf_exempt_django_app
    url = self.delete_room_url(instance.pk)

    with pytest.raises(AppError) as ex:
      _ = app.post(url, user=user)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  @pytest.mark.parametrize([
    'is_owner',
    'is_assigned',
  ], [
    (True, False),
    (False, True),
  ], ids=[
    'is-owner',
    'is-member',
  ])
  def test_can_enter_the_assigned_room(self, csrf_exempt_django_app, create_members, get_players, is_owner, is_assigned):
    _, user = get_players
    genre = factories.GenreFactory(is_enabled=True)
    creators, guests, genres = create_members
    owner = user if is_owner else creators[0]
    member = user if is_assigned else guests[1]
    for creator in creators:
      _ = factories.QuizFactory(creator=creator, genre=genre, is_completed=True)
    instance = factories.QuizRoomFactory(
      owner=owner,
      creators=[creators[0], creators[1]],
      members=[member, creators[1]],
      is_enabled=True,
    )
    instance.reset()
    app = csrf_exempt_django_app
    url = self.enter_room_url(instance.pk)
    response = app.get(url, user=user)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == url

  @pytest.mark.parametrize([
    'is_member',
    'can_use_room',
  ], [
    (False, True),
    (True, False),
  ], ids=[
    'is-not-member',
    'cannot-use-room',
  ])
  def test_cannot_enter_the_room(self, csrf_exempt_django_app, create_members, get_players, is_member, can_use_room):
    _, user = get_players
    creators, guests, genres = create_members
    member = user if is_member else guests[1]
    instance = factories.QuizRoomFactory(
      owner=creators[0],
      creators=[creators[0], creators[1]],
      members=[member, creators[1]],
      is_enabled=can_use_room,
    )
    app = csrf_exempt_django_app
    url = self.enter_room_url(instance.pk)

    with pytest.raises(AppError) as ex:
      _ = app.post(url, user=user)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

# ===============
# = UploadGenre =
# ===============
@pytest.mark.webtest
@pytest.mark.django_db
class TestUploadGenre(Common):
  genre_list_url = reverse('quiz:genre_list')
  form_view_url = reverse('quiz:upload_genre')

  def test_can_move_to_upload_page(self, csrf_exempt_django_app, get_has_manager_role_user):
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    page = app.get(self.genre_list_url, user=user)
    response = page.click('Upload genre')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.form_view_url

  def test_can_move_to_parent_page_from_upload_page(self, csrf_exempt_django_app, get_has_manager_role_user):
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    page = app.get(self.form_view_url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.genre_list_url

  @pytest.fixture(params=[
    'utf-8-with-header',
    'utf-8-without-header',
    'sjis-with-header',
    'sjis-without-header',
    'cp932-with-header',
    'cp932-without-header',
  ])
  def get_valid_form_param(self, request, get_has_manager_role_user):
    config = {
      'utf-8-with-header':    ('utf-8', True),
      'utf-8-without-header': ('utf-8', False),
      'sjis-with-header':     ('shift_jis', True),
      'sjis-without-header':  ('shift_jis', False),
      'cp932-with-header':    ('cp932', True),
      'cp932-without-header': ('cp932', False),
    }
    _, user = get_has_manager_role_user
    encoding, header = config[request.param]
    # Setup temporary file
    inputs = [
      'uploaded-genre-0x0101',
      'uploaded-genre-0x0201',
      'uploaded-genre-0x0301',
    ]
    if header:
      data = ['Genre\n']
    else:
      data = []
    data += [f'{name}\n' for name in inputs]
    # Create form data
    params = {
      'encoding': encoding,
      'csv_file': ('test-file.csv', bytes(''.join(data), encoding=encoding)), # For django-webtest format
      'header': header,
    }

    return user, params, inputs

  def test_send_post_request(self, get_valid_form_param, csrf_exempt_django_app):
    user, params, inputs = get_valid_form_param
    # Send request
    app = csrf_exempt_django_app
    forms = app.get(self.form_view_url, user=user).forms
    form = forms['genre-upload-form']
    for key, val in params.items():
      form[key] = val
    response = form.submit().follow()
    # Collect expected queryset
    queryset = models.Genre.objects.filter(name__contains='uploaded-genre-0x0')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.genre_list_url
    assert all([queryset.filter(name=name).exists() for name in inputs])

  def test_send_invalid_encoding(self, get_has_manager_role_user, csrf_exempt_django_app):
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    forms = app.get(self.form_view_url, user=user).forms
    form = forms['genre-upload-form']

    with pytest.raises(ValueError):
      form['encoding'] = 'euc-jp'

  def test_send_invalid_extensions(self, get_has_manager_role_user, csrf_exempt_django_app):
    params = {
      'encoding': 'utf-8',
      'csv_file': ('hoge.txt', bytes('hogehoge\nfogafoga\n', 'utf-8')),
    }
    err_msg = 'The extention has to be &quot;.csv&quot;.'
    # Send request
    _, user = get_has_manager_role_user
    app = csrf_exempt_django_app
    forms = app.get(self.form_view_url, user=user).forms
    form = forms['genre-upload-form']
    for key, val in params.items():
      form[key] = val
    response = form.submit()
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(errors)

# =================
# = DownloadGenre =
# =================
@pytest.mark.webtest
@pytest.mark.django_db
class TestDownloadGenre(Common):
  quiz_list_url = reverse('quiz:quiz_list')
  form_view_url = reverse('quiz:download_genre')

  def test_can_move_to_download_page(self, csrf_exempt_django_app, get_editors):
    _, user = get_editors
    app = csrf_exempt_django_app
    page = app.get(self.quiz_list_url, user=user)
    response = page.click('Download genre')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.form_view_url

  def test_can_move_to_parent_page_from_download_page(self, csrf_exempt_django_app, get_editors):
    _, user = get_editors
    app = csrf_exempt_django_app
    page = app.get(self.form_view_url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url

  @pytest.mark.parametrize([
    'filename',
    'exact_fname',
  ], [
    ('hoge-test', 'genre-hoge-test.csv'),
    ('foo-test.csv', 'genre-foo-test.csv'),
    ('.csv', 'genre-20200102-100518.csv'),
  ], ids=[
    'normal-name',
    'with-extensions',
    'only-extensions',
  ])
  def test_send_post_request(self, mocker, csrf_exempt_django_app, get_genres, get_editors, filename, exact_fname):
    genres = get_genres
    genres = models.Genre.objects.filter(pk__in=self.pk_convertor(genres)).order_by('name')
    _, user = get_editors
    # Setup mock
    mocker.patch('quiz.forms.generate_default_filename', return_value='20200102-100518')
    mocker.patch('quiz.models.Genre.objects.collect_active_genres', return_value=genres)
    # Create expected values
    lines = '\n'.join([','.join([obj.name]) for obj in genres]) + '\n'
    expected = {
      'data': bytes('Name\n' + lines, 'utf-8'),
      'filename': exact_fname,
    }
    # Send post request
    app = csrf_exempt_django_app
    forms = app.get(self.form_view_url, user=user).forms
    form = forms['genre-download-form']
    form['filename'] = filename
    response = form.submit()
    cookie = response.client.cookies.get('genre_download_status')
    attachment = response['content-disposition']
    stream = response.content

    assert expected['filename'] == urllib.parse.unquote(attachment.split('=')[1].replace('"', ''))
    assert cookie.value == 'completed'
    assert expected['data'] in stream

  def test_send_invalid_request(self, csrf_exempt_django_app, get_editors):
    _, user = get_editors
    # Send post request
    app = csrf_exempt_django_app
    forms = app.get(self.form_view_url, user=user).forms
    form = forms['genre-download-form']
    form['filename'] = '1'*129
    response = form.submit()
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert 'Ensure this value has at most 128 character' in str(errors)

# ==============
# = UploadQuiz =
# ==============
@pytest.mark.webtest
@pytest.mark.django_db
class TestUploadQuiz(Common):
  quiz_list_url = reverse('quiz:quiz_list')
  form_view_url = reverse('quiz:upload_quiz')

  def test_can_move_to_upload_page(self, csrf_exempt_django_app, get_editors):
    _, user = get_editors
    app = csrf_exempt_django_app
    page = app.get(self.quiz_list_url, user=user)
    response = page.click('Upload quiz')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.form_view_url

  def test_can_move_to_parent_page_from_upload_page(self, csrf_exempt_django_app, get_editors):
    _, user = get_editors
    app = csrf_exempt_django_app
    page = app.get(self.form_view_url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url

  @pytest.fixture(params=[
    'utf-8-with-header',
    'utf-8-without-header',
    'sjis-with-header',
    'sjis-without-header',
    'cp932-with-header',
    'cp932-without-header',
  ])
  def get_valid_form_param(self, request, get_genres, get_editors):
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
    _, user = get_editors
    encoding, header = config[request.param]
    # Set creator's members
    if user.has_manager_role():
      members = creators
      q_cond = Q(creator__pk__in=self.pk_convertor(creators), genre=genre)
    else:
      members = [user]
      q_cond = Q(creator=user, genre=genre)
    # Setup temporary file
    inputs = [
      ('q1', 'a1', True),
      ('q2', 'a2', False),
      ('q3-hoge', 'a3-foo', True),
      ('q4-x', 'a4-y', True),
    ]
    if header:
      data = ['Creator.pk,Genre,Question,Answer,IsCompleted\n']
    else:
      data = []
    data += [
      f'{creator.pk},{genre.name},{question},{answer},{is_completed}\n'
      for creator in members for question, answer, is_completed in inputs
    ]
    # Create form data
    params = {
      'encoding': encoding,
      'csv_file': ('test-file.csv', bytes(''.join(data), encoding=encoding)), # For django-webtest format
      'header': header,
    }

    return user, params, q_cond, inputs

  def test_send_post_request(self, get_valid_form_param, csrf_exempt_django_app):
    user, params, q_cond, inputs = get_valid_form_param
    # Send request
    app = csrf_exempt_django_app
    forms = app.get(self.form_view_url, user=user).forms
    form = forms['quiz-upload-form']
    for key, val in params.items():
      form[key] = val
    response = form.submit().follow()
    # Collect expected queryset
    queryset = models.Quiz.objects.filter(q_cond)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url
    assert all([
      queryset.filter(question=question, answer=answer, is_completed=is_completed).exists()
      for question, answer, is_completed in inputs
    ])

  def test_send_invalid_encoding(self, get_editors, csrf_exempt_django_app):
    _, user = get_editors
    app = csrf_exempt_django_app
    forms = app.get(self.form_view_url, user=user).forms
    form = forms['quiz-upload-form']

    with pytest.raises(ValueError):
      form['encoding'] = 'euc-jp'

  def test_send_invalid_extensions(self, get_editors, csrf_exempt_django_app):
    params = {
      'encoding': 'utf-8',
      'csv_file': ('hoge.txt', bytes('hogehoge\nfogafoga\n', 'utf-8')),
    }
    err_msg = 'The extention has to be &quot;.csv&quot;.'
    # Send request
    _, user = get_editors
    app = csrf_exempt_django_app
    forms = app.get(self.form_view_url, user=user).forms
    form = forms['quiz-upload-form']
    for key, val in params.items():
      form[key] = val
    response = form.submit()
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert err_msg in str(errors)

# ================
# = DownloadQuiz =
# ================
@pytest.mark.webtest
@pytest.mark.django_db
class TestDownloadQuiz(Common):
  quiz_list_url = reverse('quiz:quiz_list')
  form_view_url = reverse('quiz:download_quiz')

  def test_can_move_to_download_page(self, csrf_exempt_django_app, get_editors):
    _, user = get_editors
    app = csrf_exempt_django_app
    page = app.get(self.quiz_list_url, user=user)
    response = page.click('Download quiz')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.form_view_url

  def test_can_move_to_parent_page_from_download_page(self, csrf_exempt_django_app, get_editors):
    _, user = get_editors
    app = csrf_exempt_django_app
    page = app.get(self.form_view_url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url

  @pytest.mark.parametrize([
    'filename',
    'exact_fname',
    'indices',
  ], [
    ('hoge-test', 'quiz-hoge-test.csv',   [0, 1, 3, 4]), # Include all genre patterns
    ('foo-test.csv', 'quiz-foo-test.csv', [0, 2, 3, 5]), # Include all creators
    ('.csv', 'quiz-20200102-100518.csv',  range(8)),     # Include all instances
  ], ids=[
    'normal-name',
    'with-extensions',
    'only-extensions',
  ])
  def test_send_post_request(self, mocker, csrf_exempt_django_app, get_genres, get_editors, filename, exact_fname, indices):
    def generate_csv_data(instance):
      c_pk = str(instance.creator.pk)
      name = instance.genre.name
      qqq = instance.question
      ans = instance.answer
      is_c = instance.is_completed
      val = f'{c_pk},{name},{qqq},{ans},{is_c}'

      return val

    mocker.patch('quiz.forms.generate_default_filename', return_value='20200102-100518')
    genres = get_genres[:4]
    _, user = get_editors
    is_manager = user.has_manager_role()
    creator = user if not is_manager else factories.UserFactory(is_active=True, role=RoleType.CREATOR)
    others = factories.UserFactory.create_batch(3, is_active=True, role=RoleType.CREATOR)
    instances = [
      factories.QuizFactory(creator=creator,   genre=genres[0], question='qq1', answer='ans-8', is_completed=True),  # 0
      factories.QuizFactory(creator=others[0], genre=genres[1], question='qq2', answer='ans-7', is_completed=False), # 1
      factories.QuizFactory(creator=others[0], genre=genres[0], question='qq3', answer='ans-6', is_completed=True),  # 2
      factories.QuizFactory(creator=others[1], genre=genres[2], question='qq4', answer='ans-5', is_completed=False), # 3
      factories.QuizFactory(creator=others[2], genre=genres[3], question='qq5', answer='ans-4', is_completed=True),  # 4
      factories.QuizFactory(creator=others[2], genre=genres[0], question='qq6', answer='ans-3', is_completed=False), # 5
      factories.QuizFactory(creator=creator,   genre=genres[3], question='qq7', answer='ans-2', is_completed=False), # 6
      factories.QuizFactory(creator=creator,   genre=genres[2], question='qq8', answer='ans-1', is_completed=False), # 7
    ]
    all_queryset = models.Quiz.objects.filter(pk__in=self.pk_convertor(instances))
    mocker.patch('quiz.models.Quiz.objects.all', return_value=all_queryset)
    # Create expected values
    if is_manager:
      items = [instances[idx] for idx in indices]
    else:
      items = [instances[idx] for idx in indices if idx in [0, 6, 7]]
    items = models.Quiz.objects.filter(pk__in=self.pk_convertor(items)).order_by('genre__name', 'creator__screen_name')
    lines = '\n'.join([generate_csv_data(obj) for obj in items]) + '\n'
    expected = {
      'data': bytes('Creator.pk,Genre,Question,Answer,IsCompleted\n' + lines, 'utf-8'),
      'filename': exact_fname,
    }
    # Send post request
    app = csrf_exempt_django_app
    forms = app.get(self.form_view_url, user=user).forms
    form = forms['quiz-download-form']
    form['filename'] = filename
    form['quizzes'].options = [(str(instances[idx].pk), True, f'{idx}') for idx in indices]
    form['quizzes'] = [str(instances[idx].pk) for idx in indices]
    response = form.submit()
    cookie = response.client.cookies.get('quiz_download_status')
    attachment = response['content-disposition']
    stream = response.content

    assert expected['filename'] == urllib.parse.unquote(attachment.split('=')[1].replace('"', ''))
    assert cookie.value == 'completed'
    assert expected['data'] in stream

  def test_send_invalid_request(self, csrf_exempt_django_app, get_editors):
    _, user = get_editors
    # Send post request
    app = csrf_exempt_django_app
    forms = app.get(self.form_view_url, user=user).forms
    form = forms['quiz-download-form']
    form['filename'] = '1'*129
    response = form.submit()
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert 'Ensure this value has at most 128 character' in str(errors)