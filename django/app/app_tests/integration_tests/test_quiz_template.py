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

UserModel = get_user_model()

class Common:
  index_url = reverse('utils:index')
  pk_convertor = lambda _self, xs: [item.pk for item in xs]
  compare_qs = lambda _self, qs, exacts: all([val.pk == ex.pk for val, ex in zip(qs, exacts)])

  @pytest.fixture(params=['superuser', 'staff', 'manager', 'creator', 'guest'], scope='module')
  def get_users(self, django_db_blocker, request):
    key = request.param
    configs = {
      'superuser': {'role': RoleType.GUEST, 'is_staff': True, 'is_superuser': True},
      'staff': {'role': RoleType.GUEST, 'is_staff': True, 'is_superuser': False},
      'manager': {'role': RoleType.MANAGER},
      'creator': {'role': RoleType.CREATOR},
      'guest':   {'role': RoleType.GUEST},
    }
    with django_db_blocker.unblock():
      kwargs = configs[key]
      user = factories.UserFactory(is_active=True, **kwargs)

    return user

  @pytest.fixture(params=['superuser', 'manager'], scope='module')
  def get_managers(self, django_db_blocker, request):
    key = request.param
    configs = {
      'superuser': {'role': RoleType.GUEST, 'is_staff': True, 'is_superuser': True},
      'manager': {'role': RoleType.MANAGER},
    }
    with django_db_blocker.unblock():
      kwargs = configs[key]
      user = factories.UserFactory(is_active=True, **kwargs)

    return user

  @pytest.fixture(params=['superuser', 'manager', 'creator'], scope='module')
  def get_editors(self, django_db_blocker, request):
    key = request.param
    configs = {
      'superuser': {'role': RoleType.GUEST, 'is_staff': True, 'is_superuser': True},
      'manager': {'role': RoleType.MANAGER},
      'creator': {'role': RoleType.CREATOR},
    }
    with django_db_blocker.unblock():
      kwargs = configs[key]
      user = factories.UserFactory(is_active=True, **kwargs)

    return user

  @pytest.fixture(params=['creator', 'guest'], scope='module')
  def get_players(self, django_db_blocker, request):
    key = request.param
    configs = {
      'creator': {'role': RoleType.CREATOR},
      'guest': {'role': RoleType.GUEST},
    }
    with django_db_blocker.unblock():
      kwargs = configs[key]
      user = factories.UserFactory(is_active=True, **kwargs)

    return user

  @pytest.fixture(params=['creator'], scope='module')
  def get_creator(self, django_db_blocker, request):
    key = request.param
    with django_db_blocker.unblock():
      user = factories.UserFactory(is_active=True, role=RoleType.CREATOR)

    return user

  @pytest.fixture(params=['guest'], scope='module')
  def get_guest(self, django_db_blocker, request):
    key = request.param
    with django_db_blocker.unblock():
      user = factories.UserFactory(is_active=True, role=RoleType.GUEST)

    return user

  @pytest.fixture(scope='module')
  def get_genres(self, django_db_blocker):
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

# =========
# = Genre =
# =========
@pytest.mark.webtest
@pytest.mark.django_db
class TestGenre(Common):
  genre_list_url = reverse('quiz:genre_list')
  create_genre_url = reverse('quiz:create_genre')
  update_genre_url = lambda _self, pk: reverse('quiz:update_genre', kwargs={'pk': pk})

  def test_can_move_to_genre_page(self, csrf_exempt_django_app, get_managers):
    user = get_managers
    app = csrf_exempt_django_app
    page = app.get(self.index_url, user=user)
    response = page.click('Quiz genre')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.genre_list_url

  def test_cannot_move_to_genre_page(self, csrf_exempt_django_app, get_players):
    user = get_players
    app = csrf_exempt_django_app
    page = app.get(self.index_url, user=user)

    with pytest.raises(IndexError):
      _ = page.click('Quiz genre')

  def test_can_move_to_genre_create_page(self, csrf_exempt_django_app, get_managers):
    user = get_managers
    app = csrf_exempt_django_app
    page = app.get(self.genre_list_url, user=user)
    response = page.click('Create a new genre')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.create_genre_url

  def test_can_move_to_parent_page_from_genre_create_page(self, csrf_exempt_django_app, get_managers):
    user = get_managers
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
  def test_send_post_request(self, csrf_exempt_django_app, get_managers, config, is_enabled):
    user = get_managers
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

  def test_can_move_to_genre_update_page(self, csrf_exempt_django_app, get_genres, get_managers):
    instance = get_genres[0]
    user = get_managers
    app = csrf_exempt_django_app
    page = app.get(self.genre_list_url, user=user)
    output_url = self.update_genre_url(instance.pk)
    response = page.click('Edit', href=output_url)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == output_url

  def test_can_move_to_parent_page_from_genre_update_page(self, csrf_exempt_django_app, get_genres, get_managers):
    instance = get_genres[0]
    user = get_managers
    app = csrf_exempt_django_app
    url = self.update_genre_url(instance.pk)
    page = app.get(url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.genre_list_url

  def test_update_genre(self, csrf_exempt_django_app, get_managers):
    instance = factories.GenreFactory(is_enabled=False)
    user = get_managers
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
  paginate_by = 15

  def test_can_move_to_quiz_page(self, csrf_exempt_django_app, get_editors):
    user = get_editors
    app = csrf_exempt_django_app
    page = app.get(self.index_url, user=user)
    response = page.click('Check/Create/Update quizzes')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url

  def test_cannot_move_to_quiz_page(self, csrf_exempt_django_app, get_guest):
    user = get_guest
    app = csrf_exempt_django_app
    page = app.get(self.index_url, user=user)

    with pytest.raises(IndexError):
      _ = page.click('Check/Create/Update quizzes')

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

  def test_cannot_move_to_quiz_create_page(self, csrf_exempt_django_app, get_managers):
    user = get_managers
    app = csrf_exempt_django_app
    page = app.get(self.quiz_list_url, user=user)

    with pytest.raises(IndexError):
      _ = page.click('Create a new quiz')

  @pytest.fixture
  def create_quizzes(self, django_db_blocker, get_genres, get_creator):
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
      all_queryset = models.Quiz.objects.filter(pk__in=self.pk_convertor(instances))

    return creator, others[1], all_queryset

  def test_check_quiz_queryset_for_manager(self, csrf_exempt_django_app, mocker, create_quizzes, get_managers):
    creator, _, all_queryset = create_quizzes
    user = get_managers
    app = csrf_exempt_django_app
    mocker.patch('quiz.views.QuizListPage.get_queryset', return_value=all_queryset)
    response = app.get(self.quiz_list_url, user=user)
    quizzes = response.context['quizzes']
    estimated = models.Quiz.objects.filter(pk__in=[_quiz.pk for _quiz in quizzes])
    expected = all_queryset[:self.paginate_by] if len(all_queryset) > self.paginate_by else all_queryset

    assert response.status_code == status.HTTP_200_OK
    assert estimated.count() == len(expected)
    assert self.compare_qs(estimated, expected)

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

  def test_check_filtering_method_for_manager(self, csrf_exempt_django_app, mocker, get_genres, create_quizzes, get_managers):
    genres = get_genres
    creator, _, all_queryset = create_quizzes
    user = get_managers
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

  def test_can_move_to_quiz_update_page(self, csrf_exempt_django_app, get_managers):
    instance = factories.QuizFactory()
    user = get_managers
    app = csrf_exempt_django_app
    page = app.get(self.quiz_list_url, user=user)
    output_url = self.update_quiz_url(instance.pk)
    response = page.click('Edit', href=output_url)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == output_url

  def test_can_move_to_parent_page_from_quiz_update_page(self, csrf_exempt_django_app, get_managers):
    instance = factories.QuizFactory()
    user = get_managers
    app = csrf_exempt_django_app
    url = self.update_quiz_url(instance.pk)
    page = app.get(url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url

  def test_cannot_move_to_other_creators_update_page(self, csrf_exempt_django_app, create_quizzes):
    user, other, _ = create_quizzes
    instance = other.quizzes.all().first()
    app = csrf_exempt_django_app
    url = self.update_quiz_url(instance.pk)

    with pytest.raises(AppError) as ex:
      _ = app.get(url, user=user)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  def test_update_quiz_for_creator(self, csrf_exempt_django_app, create_quizzes):
    user, _, _ = create_quizzes
    instance = user.quizzes.all().first()
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

  def test_update_quiz_for_manager(self, csrf_exempt_django_app, create_quizzes, get_managers):
    _, other, _ = create_quizzes
    user = get_managers
    instance = other.quizzes.all().first()
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
    user = get_users
    instance = creator.quizzes.all().first()
    app = csrf_exempt_django_app
    url = self.delete_quiz_url(instance.pk)

    with pytest.raises(AppError) as ex:
      _ = app.get(url, user=user)

    assert any([
      str(status.HTTP_403_FORBIDDEN) in ex.value.args[0],
      str(status.HTTP_405_METHOD_NOT_ALLOWED) in ex.value.args[0],
    ])

  def test_delete_quiz_for_manager(self, csrf_exempt_django_app, create_quizzes, get_managers):
    _, other, _ = create_quizzes
    user = get_managers
    instance = other.quizzes.all().first()
    app = csrf_exempt_django_app
    url = self.delete_quiz_url(instance.pk)
    response = app.post(url, user=user).follow()
    queryset = models.Quiz.objects.filter(pk__in=[instance.pk])

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url
    assert queryset.count() == 0

  def test_delete_quiz_for_creator(self, csrf_exempt_django_app, create_quizzes):
    user, _, _ = create_quizzes
    instance = user.quizzes.all().first()
    app = csrf_exempt_django_app
    url = self.delete_quiz_url(instance.pk)
    response = app.post(url, user=user).follow()
    queryset = models.Quiz.objects.filter(pk__in=[instance.pk])

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.quiz_list_url
    assert queryset.count() == 0

  def test_delete_quiz_for_other_creator(self, csrf_exempt_django_app, create_quizzes):
    user, other, _ = create_quizzes
    instance = other.quizzes.all().first()
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
    user = get_users
    app = csrf_exempt_django_app
    page = app.get(self.index_url, user=user)
    response = page.click('Quiz room')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.room_list_url

  def test_can_move_to_room_create_page(self, csrf_exempt_django_app, get_players):
    user = get_players
    app = csrf_exempt_django_app
    page = app.get(self.room_list_url, user=user)
    response = page.click('Create a new quiz room')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.create_room_url

  def test_can_move_to_parent_page_from_room_create_page(self, csrf_exempt_django_app, get_players):
    user = get_players
    app = csrf_exempt_django_app
    page = app.get(self.create_room_url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.room_list_url

  def test_cannot_move_to_room_create_page(self, csrf_exempt_django_app, get_managers):
    user = get_managers
    app = csrf_exempt_django_app
    page = app.get(self.room_list_url, user=user)

    with pytest.raises(IndexError):
      _ = page.click('Create a new quiz room')

  @pytest.fixture(scope='class')
  def create_members(self, get_genres, django_db_blocker):
    with django_db_blocker.unblock():
      creators = list(factories.UserFactory.create_batch(4, is_active=True, role=RoleType.CREATOR))
      guests = list(factories.UserFactory.create_batch(3, is_active=True, role=RoleType.GUEST))
      genres = get_genres

    return creators, guests, genres

  @pytest.fixture
  def create_rooms(self, django_db_blocker, get_players, create_members):
    with django_db_blocker.unblock():
      creators, guests, genres = create_members
      members = creators + guests
      user = get_players
      configs = [
        ### Not relevant ###
        {'owner': creators[0], 'name': 'target-room', 'creators': [creators[1].pk, creators[2].pk], 'genres': [genres[0].pk, genres[3].pk], 'members': self.pk_convertor(guests), 'is_enabled': False},
        # The user includes members
        {'owner': creators[1], 'name': 'test-room1', 'creators': [creators[2].pk, creators[3].pk], 'members': self.pk_convertor(guests+[user]), 'is_enabled': True},
        ### Not relevant ###
        {'owner': guests[0], 'name': 'test-room2', 'creators': [creators[0].pk, creators[3].pk], 'genres': [genres[5].pk], 'members': self.pk_convertor(members), 'is_enabled': True},
        # The user includes members
        {'owner': guests[1], 'name': 'test-room3', 'genres': [genres[3].pk, genres[4].pk], 'members': self.pk_convertor(members+[user]), 'is_enabled': False},
        # The user is an owner
        {'owner': user, 'name': 'target-room', 'creators': [creators[0].pk], 'members': self.pk_convertor(guests), 'is_enabled': True},
        # The user is an owner
        {'owner': user, 'name': 'test-room4', 'creators': [creators[1].pk], 'members': self.pk_convertor(creators), 'is_enabled': False},
      ]
      instances = [factories.QuizRoomFactory(max_question=10, **kwargs) for kwargs in configs]
      all_queryset = models.QuizRoom.objects.filter(pk__in=self.pk_convertor(instances))

    return user, guests[0], all_queryset

  def test_check_room_queryset_for_manager(self, csrf_exempt_django_app, mocker, create_rooms, get_managers):
    user = get_managers
    _, _, all_queryset = create_rooms
    app = csrf_exempt_django_app
    mocker.patch('quiz.models.QuizRoom.objects.all', return_value=all_queryset)
    response = app.get(self.room_list_url, user=user)
    rooms = models.QuizRoom.objects.filter(pk__in=[_room.pk for _room in response.context['rooms']]).order_by('pk')
    expected = all_queryset.order_by('pk')

    assert response.status_code == status.HTTP_200_OK
    assert rooms.count() == expected.count()
    assert self.compare_qs(rooms, expected)

  def test_check_room_queryset_for_player(self, csrf_exempt_django_app, create_rooms):
    user, _, all_queryset = create_rooms
    app = csrf_exempt_django_app
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
    'name-target-room-and-manager-2-player-1',
    'name-test-room-and-manager-4-player-2',
    'name-room-and-manager-6-player-3',
  ])
  def test_check_filtering_method(self, csrf_exempt_django_app, mocker, create_rooms, get_users, name, pair):
    _u_tmp = get_users
    is_player = _u_tmp.is_player()
    owner, _, all_queryset = create_rooms
    user = owner if is_player else _u_tmp
    expected_count = pair[is_player]
    app = csrf_exempt_django_app
    mocker.patch('quiz.models.QuizRoom.objects.all', return_value=all_queryset)
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
    user = get_players
    app = csrf_exempt_django_app
    creators, guests, genres = create_members
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

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.room_list_url
    assert all([pk in creator_ids for pk in self.pk_str_convertor(instance.creators.all())])
    assert all([pk in genre_ids for pk in self.pk_str_convertor(instance.genres.all())])
    assert all([pk in member_ids for pk in self.pk_str_convertor(instance.members.all())])
    assert not instance.is_enabled

  def test_invalid_create_request(self, csrf_exempt_django_app, create_members, get_players):
    user = get_players
    app = csrf_exempt_django_app
    _, guests, _ = create_members
    forms = app.get(self.create_room_url, user=user).forms
    form = forms['room-form']
    form['name'] = 'test-room'
    form['members'] = self.pk_str_convertor([guests[0], guests[1]])
    form['max_question'] = 1
    form['is_enabled'] = True
    response = form.submit()
    errors = response.context['form'].errors

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.create_room_url
    assert 'You have to assign at least one of genres and creators to the quiz room.' in str(errors)

  def test_can_move_to_room_update_page(self, csrf_exempt_django_app, create_members, get_managers):
    creators, guests, genres = create_members
    _ = factories.QuizRoomFactory(
      owner=creators[0],
      genres=[genres[1].pk, genres[2].pk],
      members=[guests[0].pk],
    )
    user = get_managers
    app = csrf_exempt_django_app
    page = app.get(self.room_list_url, user=user)
    rooms = page.context['rooms']
    output_url = self.update_room_url(rooms[0].pk)
    response = page.click('Edit', href=output_url)

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == output_url

  def test_can_move_to_parent_page_from_room_update_page(self, csrf_exempt_django_app, create_members, get_managers):
    creators, guests, genres = create_members
    instance = factories.QuizRoomFactory(
      owner=creators[0],
      genres=[genres[1].pk, genres[2].pk],
      members=[guests[0].pk],
    )
    user = get_managers
    app = csrf_exempt_django_app
    url = self.update_room_url(instance.pk)
    page = app.get(url, user=user)
    response = page.click('Cancel')

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.room_list_url

  def test_cannot_move_to_other_creators_update_page(self, csrf_exempt_django_app, create_rooms):
    user, other, _ = create_rooms
    instance = other.quiz_rooms.all().first()
    app = csrf_exempt_django_app
    url = self.update_room_url(instance.pk)

    with pytest.raises(AppError) as ex:
      _ = app.get(url, user=user)

    assert str(status.HTTP_403_FORBIDDEN) in ex.value.args[0]

  @pytest.fixture
  def get_being_able_to_modify_rooms(self, django_db_blocker, get_players, create_members):
    with django_db_blocker.unblock():
      creators, guests, genres = create_members
      members = creators + guests
      user = get_players
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
    target = user.quiz_rooms.all().first()
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

  def test_update_room_for_manager(self, csrf_exempt_django_app, create_members, get_being_able_to_modify_rooms, get_managers):
    creators, guests, genres = create_members
    _, other = get_being_able_to_modify_rooms
    _ = factories.QuizFactory(creator=creators[0], genre=genres[0], is_completed=True)
    _ = factories.QuizFactory(creator=creators[2], genre=genres[0], is_completed=True)
    user = get_managers
    target = other.quiz_rooms.all().first()
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
    user = get_users
    instance = creator.quiz_rooms.all().first()
    app = csrf_exempt_django_app
    url = self.delete_room_url(instance.pk)

    with pytest.raises(AppError) as ex:
      _ = app.get(url, user=user)

    assert any([
      str(status.HTTP_403_FORBIDDEN) in ex.value.args[0],
      str(status.HTTP_405_METHOD_NOT_ALLOWED) in ex.value.args[0],
    ])

  def test_can_delete_room_for_manager(self, csrf_exempt_django_app, create_members, get_managers):
    creators, guests, genres = create_members
    instance = factories.QuizRoomFactory(
      owner=guests[0],
      creators=[creators[0], creators[1]],
      members=[guests[1], creators[1]],
      is_enabled=False,
    )
    user = get_managers
    app = csrf_exempt_django_app
    url = self.delete_room_url(instance.pk)
    response = app.post(url, user=user).follow()
    queryset = models.QuizRoom.objects.filter(pk__in=[instance.pk])

    assert response.status_code == status.HTTP_200_OK
    assert get_current_path(response) == self.room_list_url
    assert queryset.count() == 0

  def test_can_delete_room_for_player(self, csrf_exempt_django_app, create_members, get_players):
    user = get_players
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
    user = get_users
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
    user = get_players
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
    user = get_players
    creators, guests, genres = create_members
    owner = user if is_owner else creators[0]
    member = user if is_assigned else guests[1]
    instance = factories.QuizRoomFactory(
      owner=owner,
      creators=[creators[0], creators[1]],
      members=[member, creators[1]],
      is_enabled=True,
    )
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
    user = get_players
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