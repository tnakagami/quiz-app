import pytest
import pytest_asyncio
from datetime import datetime
from django.conf import settings
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from account.models import RoleType
from quiz import models, consumers
from app_tests import factories

UserModel = get_user_model()

class DummyBaseQuizState:
  def __init__(self, player_ids):
    self.score = None
    self.quiz = None
    self.players = {key: False for key in player_ids}
    self.answers = {}
    self.current_time = None
  def update_score(self, score):
    self.score = score
  def update_player(self, pk, do_delete=False):
    pass
  def has_player(self):
    return False
  @database_sync_to_async
  def get_quiz(self, max_question):
    return 'hoge', 2
  def update_member_status(self, pk):
    return True
  @database_sync_to_async
  def answering_phase(self):
    pass
  @database_sync_to_async
  def can_answer(self):
    return True
  def update_answer(self, pk, answer):
    pass
  @database_sync_to_async
  def received_all_answers_phase(self):
    pass
  @database_sync_to_async
  def get_answers(self):
    return {}, 'foo'
  @database_sync_to_async
  def update_state(self, max_question, judgement):
    return {}, True

class AuthWebsocketCommunicator(WebsocketCommunicator):
  async def __new__(cls, *args, **kwargs):
    instance = super().__new__(cls)
    await instance.__init__(*args, **kwargs)

    return instance

  async def __init__(self, application, path, headers=None, user=None, *args, **kwargs):
    self._session_key = None
    self._session_cookie = b''

    if user is not None:
      await self.force_login(user)
      cookie_header = (b'cookie', self._session_cookie)

      if headers:
        for idx, header in enumerate(headers):
          if header[0] == cookie_header[0]:
            headers[idx] = (cookie_header[0], b'; '.join((cookie_header[1], headers[idx][1])))
            break
        else:
          headers.append(cookie_header)
      else:
        headers = [cookie_header]

    super().__init__(application, path, headers=headers, *args, **kwargs)
    self.scope['user'] = user

  def _login(self, user, backend=None):
    from django.http import HttpRequest, SimpleCookie
    from importlib import import_module
    from django.contrib.auth import login

    engine = import_module(settings.SESSION_ENGINE)

    # Create a fake request to store login details.
    request = HttpRequest()
    request.session = engine.SessionStore()
    login(request, user, backend)

    # Save the session values.
    request.session.save()
    self.session_key = request.session.session_key

    # Create a cookie to represent the session.
    session_cookie = settings.SESSION_COOKIE_NAME
    cookies = SimpleCookie()
    cookies[session_cookie] = self.session_key
    cookie_data = {
      'max-age': None,
      'path': '/',
      'domain': settings.SESSION_COOKIE_DOMAIN,
      'secure': settings.SESSION_COOKIE_SECURE or None,
      'expires': None,
    }
    cookies[session_cookie].update(cookie_data)
    self._session_cookie = cookies

  @database_sync_to_async
  def force_login(self, user, backend=None):
    def get_backend():
      from django.contrib.auth import load_backend

      for backend_path in settings.AUTHENTICATION_BACKENDS:
        backend = load_backend(backend_path)

        if hasattr(backend, 'get_user'):
          return backend_path

    if backend is None:
      backend = get_backend()
    user.backend = backend
    self._login(user, backend)

@pytest.fixture(scope='module')
def aget_guest(django_db_blocker):
  @database_sync_to_async
  def inner():
    with django_db_blocker.unblock():
      user = factories.UserFactory(is_active=True, role=RoleType.GUEST, screen_name='guest-owner')

    return user

  return inner

@pytest.fixture(scope='module')
def aget_creator(django_db_blocker):
  @database_sync_to_async
  def inner():
    with django_db_blocker.unblock():
      user = factories.UserFactory(is_active=True, role=RoleType.CREATOR, screen_name='creator-owner')

    return user

  return inner

@pytest.fixture(scope='module')
def get_room_instances(django_db_blocker):
  @database_sync_to_async
  def inner(owner):
    with django_db_blocker.unblock():
      genres = factories.GenreFactory.create_batch(3, is_enabled=True)
      genres = models.Genre.objects.filter(pk__in=[obj.pk for obj in genres])
      creators = list(factories.UserFactory.create_batch(3, is_active=True, role=RoleType.GUEST))
      guests = list(factories.UserFactory.create_batch(4, is_active=True, role=RoleType.GUEST))
      # Update screen name
      for idx, creator in enumerate(creators):
        creator.screen_name = f'creator{idx}'
        creator.save()
      for idx, guest in enumerate(guests):
        guest.screen_name = f'guest{idx}'
        guest.save()
      # Note: creators[1] and guests[2] are not members
      members = [creators[0], creators[2], guests[0], guests[1], guests[3]]
      # Create quizzes
      quizzes = [
        factories.QuizFactory(creator=creators[0], genre=genres[0], is_completed=True),  # 0
        factories.QuizFactory(creator=creators[1], genre=genres[0], is_completed=True),  # 1
        factories.QuizFactory(creator=creators[2], genre=genres[0], is_completed=False), # 2 Is not selected
        factories.QuizFactory(creator=creators[0], genre=genres[1], is_completed=True),  # 3
        factories.QuizFactory(creator=creators[1], genre=genres[1], is_completed=True),  # 4
        factories.QuizFactory(creator=creators[2], genre=genres[1], is_completed=True),  # 5 Is not selected
        factories.QuizFactory(creator=creators[0], genre=genres[2], is_completed=True),  # 6
        factories.QuizFactory(creator=creators[1], genre=genres[2], is_completed=True),  # 7
        factories.QuizFactory(creator=creators[2], genre=genres[2], is_completed=True),  # 8
      ]
      room = factories.QuizRoomFactory(
        name='test-consumer-room',
        owner=owner,
        creators=[creators[0], creators[1]],
        genres=[genres[0], genres[2]],
        members=list(members),
        max_question=4,
        is_enabled=True,
      )
      room.reset()
      room.score.index = 3
      room.score.status = models.QuizStatusType.ANSWERING
      room.score.save()

    return owner, creators, guests, room

  return inner


class Common:
  pk_convertor = lambda _self, xs: [item.pk for item in xs]

  @database_sync_to_async
  def aget_score(self, room):
    return models.Score.objects.get(room=room)

  @database_sync_to_async
  def aget_score_status(self, score):
    return score.status

  @database_sync_to_async
  def aget_score_index(self, score):
    return score.index

  @database_sync_to_async
  def aget_score_sequence(self, score):
    return score.sequence

  @database_sync_to_async
  def aget_score_detail(self, score):
    return score.detail

  @database_sync_to_async
  def aget_player_ids(self, room):
    pks = room.members.all().values_list('pk', flat=True)
    player_ids = list(map(lambda val: f'user{val}', pks))

    return player_ids

@pytest.mark.quiz
@pytest.mark.consumer
@pytest.mark.django_db
@pytest.mark.filterwarnings('ignore:valid_channel_name is deprecated')
@pytest.mark.filterwarnings('ignore:valid_group_name is deprecated')
class TestQuizConsumer(Common):
  @pytest.fixture
  def mock_logger_and_now_method(self, mocker):
    class DummyLogger:
      def __init__(self):
        self.message = None
      def error(self, message):
        self.message = message

    mock_logger = mocker.patch('quiz.consumers.getLogger', return_value=DummyLogger())
    mocker.patch('quiz.consumers.convert_timezone', return_value='2024-07-03 12:51:43')

    return mock_logger, mocker

  async def aget_communicator(self, room, user):
    from channels.routing import URLRouter
    from quiz.routing import websocket_urlpatterns
    # Create communicator
    communicator = await AuthWebsocketCommunicator(URLRouter(websocket_urlpatterns), f'ws/quizroom/{room.pk}', user=user)

    return communicator

  @pytest.mark.parametrize([
    'access_type',
  ], [
    ('creator', ),
    ('guest', ),
    ('owner-with-creator', ),
    ('owner-with-guest',),
  ], ids=[
    'valid-creator',
    'valid-guest',
    'valid-owner-with-creator',
    'valid-owner-with-guest',
  ])
  @pytest.mark.asyncio
  async def test_check_valid_connect(self, aget_guest, aget_creator, get_room_instances, access_type):
    if access_type == 'valid-owner-with-creator':
      owner = await aget_creator()
    else:
      owner = await aget_guest()
    _, creators, guests, room = await get_room_instances(owner)
    patterns = {
      'creator': creators[2],
      'guest': guests[3],
      'owner-with-creator': owner,
      'owner-with-guest': owner,
    }
    user = patterns[access_type]
    communicator = await self.aget_communicator(room, user)
    connected, _ = await communicator.connect()
    await communicator.disconnect()

    assert connected

  @pytest.mark.parametrize([
    'access_type',
  ], [
    ('creator',),
    ('guest',),
  ], ids=[
    'invalid-creator',
    'invalid-guest',
  ])
  @pytest.mark.asyncio
  async def test_check_invalid_connect(self, aget_guest, get_room_instances, access_type):
    owner = await aget_guest()
    _, creators, guests, room = await get_room_instances(owner)
    patterns = {
      'creator': creators[1],
      'guest': guests[2],
    }
    user = patterns[access_type]
    communicator = await self.aget_communicator(room, user)

    with pytest.raises(TimeoutError):
      _ = await communicator.connect()

  @pytest.mark.asyncio
  async def test_connect_exception(self, mock_logger_and_now_method, aget_guest, get_room_instances):
    logger, mocker = mock_logger_and_now_method
    user = await aget_guest()
    _, _, _, room = await get_room_instances(user)
    communicator = await self.aget_communicator(room, user)
    err_msg = f'[quiz-{room.pk}]Connect: Invalid'
    mocker.patch('quiz.consumers.QuizConsumer.accept', side_effect=Exception('Invalid'))
    # Call connect method
    with pytest.raises(TimeoutError):
      _ = await communicator.connect()
    message = logger.return_value.message

    assert message == err_msg

  @pytest.mark.asyncio
  async def test_check_greeting_messages(self, aget_guest, get_room_instances):
    owner = await aget_guest()
    _, creators, _, room = await get_room_instances(owner)
    comm_owner = await self.aget_communicator(room, owner)
    comm_member = await self.aget_communicator(room, creators[2])
    # Connect and receive messages
    connected_owner, _ = await comm_owner.connect()
    join_msg_for_owner_only = await comm_owner.receive_json_from()
    connected_member, _ = await comm_member.connect()
    join_msg_owner = await comm_owner.receive_json_from()
    join_msg_member = await comm_member.receive_json_from()
    # Disconnect
    await comm_owner.disconnect()
    leave_msg_member = await comm_member.receive_json_from()
    await comm_member.disconnect()

    assert connected_owner
    assert connected_member
    assert all(['message' in item.keys() for item in [join_msg_for_owner_only, join_msg_owner, join_msg_member, leave_msg_member]])
    assert 'Join guest-owner to test-consumer-room' == join_msg_for_owner_only['message']
    assert 'Join creator2 to test-consumer-room' == join_msg_owner['message']
    assert 'Join creator2 to test-consumer-room' == join_msg_member['message']
    assert 'Leave guest-owner from test-consumer-room' == leave_msg_member['message']

  @pytest.mark.asyncio
  async def test_check_post_accept_and_post_disconnect(self, monkeypatch, aget_guest, get_room_instances):
    # Define test code
    accepted_states = {}
    disconnected_states = {}

    def get_callback(name):
      return accepted_states.get(name)
    def set_callback(name, instance):
      accepted_states[name] = instance
    def del_callback(name):
      disconnected_states[name] = accepted_states[name]

    monkeypatch.setattr('quiz.consumers.g_quizstates.get_state', get_callback)
    monkeypatch.setattr('quiz.consumers.g_quizstates.set_state', set_callback)
    monkeypatch.setattr('quiz.consumers.g_quizstates.del_state', del_callback)
    owner = await aget_guest()
    _, _, _, room = await get_room_instances(owner)
    communicator = await self.aget_communicator(room, owner)
    _ = await communicator.connect()
    await communicator.disconnect()
    key = f'quiz-{room.pk}'

    assert len(accepted_states) == 1
    assert len(disconnected_states) == 1
    assert key in accepted_states.keys()
    assert key in disconnected_states.keys()
    assert isinstance(accepted_states[key], consumers.QuizState)
    assert isinstance(disconnected_states[key], consumers.QuizState)
    assert id(accepted_states[key]) == id(disconnected_states[key])

  @pytest.mark.asyncio
  async def test_send_group_message_exception(self, mock_logger_and_now_method, aget_guest, get_room_instances):
    logger, mocker = mock_logger_and_now_method
    user = await aget_guest()
    _, _, _, room = await get_room_instances(user)
    communicator = await self.aget_communicator(room, user)
    err_msg = f'[quiz-{room.pk}]Send group message: Invalid'
    mocker.patch('quiz.consumers.QuizConsumer.send_json', side_effect=Exception('Invalid'))
    # Call connect and disconnect method
    _ = await communicator.connect()
    is_no_data = await communicator.receive_nothing()
    await communicator.disconnect()
    message = logger.return_value.message

    assert is_no_data
    assert message == err_msg

  @pytest.mark.asyncio
  async def test_receive_json_exception(self, mock_logger_and_now_method, aget_guest, get_room_instances):
    logger, _ = mock_logger_and_now_method
    user = await aget_guest()
    _, _, _, room = await get_room_instances(user)
    communicator = await self.aget_communicator(room, user)
    err_msg = f'[quiz-{room.pk}] '
    # Send message
    _ = await communicator.connect()
    await communicator.send_json_to({'command': 'hoge', 'data': None})
    await communicator.disconnect()
    message = logger.return_value.message

    assert err_msg in message

  @pytest_asyncio.fixture(params=['is-owner', 'is-not-owner'])
  async def common_process(self, aget_guest, get_room_instances, request):
    is_owner = ('is-owner' == request.param)
    owner = await aget_guest()
    _, creators, _, room = await get_room_instances(owner)
    owner_socket = await self.aget_communicator(room, owner)
    member_socket = await self.aget_communicator(room, creators[2])
    # Call reset method
    _ = await owner_socket.connect()
    _ = await owner_socket.receive_json_from()
    _ = await member_socket.connect()
    _ = await owner_socket.receive_json_from()
    _ = await member_socket.receive_json_from()

    yield is_owner, owner_socket, member_socket, room

    await owner_socket.disconnect()
    await member_socket.disconnect()

  @pytest.mark.asyncio
  async def test_check_reset_quiz_method(self, common_process):
    is_owner, owner_socket, member_socket, room = common_process
    data = {'command': 'resetQuiz'}
    # Call reset method
    if is_owner:
      expected_status = models.QuizStatusType.START.value
      expected_index = 1
      await owner_socket.send_json_to(data)
      owner_msg = await owner_socket.receive_json_from()
      member_msg = await member_socket.receive_json_from()
      callback = lambda msg: msg['type'] == 'resetCompleted'
    else:
      expected_status = models.QuizStatusType.ANSWERING.value
      expected_index = 3
      await member_socket.send_json_to(data)
      owner_msg = await owner_socket.receive_nothing()
      member_msg = await member_socket.receive_nothing()
      callback = lambda msg: msg
    # Get score data
    score = await self.aget_score(room=room)

    assert callback(owner_msg)
    assert callback(member_msg)
    assert await self.aget_score_status(score) == expected_status
    assert await self.aget_score_index(score) == expected_index

  @pytest.mark.asyncio
  async def test_get_next_quiz_method(self, monkeypatch, common_process):
    is_owner, owner_socket, member_socket, room = common_process
    player_ids = await self.aget_player_ids(room)

    class DummyQStat(DummyBaseQuizState):
      @database_sync_to_async
      def get_quiz(self, max_question):
        return 'hogehoge', 4

    def get_callback(name):
      return DummyQStat(player_ids)
    def del_callback(name):
      pass

    # Define test code
    monkeypatch.setattr('quiz.consumers.g_quizstates.get_state', get_callback)
    monkeypatch.setattr('quiz.consumers.g_quizstates.del_state', del_callback)
    data = {'command': 'getNextQuiz'}
    # Call get_next_quiz method
    if is_owner:
      await owner_socket.send_json_to(data)
      owner_msg = await owner_socket.receive_json_from()
      member_msg = await member_socket.receive_json_from()
      pairs = {
        'type': 'sentNextQuiz',
        'data': 'hogehoge',
        'index': 4,
        'message': 'The next quiz is received.',
      }
      callback = lambda msg: all([msg[key] == val for key, val in pairs.items()])
    else:
      await member_socket.send_json_to(data)
      owner_msg = await owner_socket.receive_nothing()
      member_msg = await member_socket.receive_nothing()
      callback = lambda msg: msg

    assert callback(owner_msg)
    assert callback(member_msg)

  @pytest.mark.parametrize([
    'is_completed',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'is-completed',
    'is-not-completed',
  ])
  @pytest.mark.asyncio
  async def test_received_quiz_method(self, monkeypatch, common_process, is_completed):
    is_owner, owner_socket, member_socket, room = common_process
    player_ids = await self.aget_player_ids(room)

    class DummyQStat(DummyBaseQuizState):
      def update_member_status(self, pk):
        return is_completed

    def get_callback(name):
      return DummyQStat(player_ids)
    def del_callback(name):
      pass

    # Define test code
    monkeypatch.setattr('quiz.consumers.g_quizstates.get_state', get_callback)
    monkeypatch.setattr('quiz.consumers.g_quizstates.del_state', del_callback)
    data = {'command': 'receivedQuiz'}
    # Call received_quiz method
    if is_owner:
      await owner_socket.send_json_to(data)
    else:
      await member_socket.send_json_to(data)
    if is_completed:
      owner_msg = await owner_socket.receive_json_from()
      member_msg = await member_socket.receive_json_from()
      pairs = {
        'type': 'sentAllQuizzes',
        'message': 'All players received the quiz.',
      }
      callback = lambda msg: all([msg[key] == val for key, val in pairs.items()])
    else:
      owner_msg = await owner_socket.receive_nothing()
      member_msg = await member_socket.receive_nothing()
      callback = lambda msg: msg

    assert callback(owner_msg)
    assert callback(member_msg)

  @pytest.mark.asyncio
  async def test_start_answer_method(self, monkeypatch, common_process):
    is_owner, owner_socket, member_socket, room = common_process
    player_ids = await self.aget_player_ids(room)

    def get_callback(name):
      return DummyBaseQuizState(player_ids)
    def del_callback(name):
      pass

    # Define test code
    monkeypatch.setattr('quiz.consumers.g_quizstates.get_state', get_callback)
    monkeypatch.setattr('quiz.consumers.g_quizstates.del_state', del_callback)
    data = {'command': 'startAnswer'}
    # Call start_answer method
    if is_owner:
      await owner_socket.send_json_to(data)
      owner_msg = await owner_socket.receive_json_from()
      member_msg = await member_socket.receive_json_from()
      callback = lambda msg: msg['type'] == 'startedAnswering'
    else:
      await member_socket.send_json_to(data)
      owner_msg = await owner_socket.receive_nothing()
      member_msg = await member_socket.receive_nothing()
      callback = lambda msg: msg

    assert callback(owner_msg)
    assert callback(member_msg)

  @pytest.mark.parametrize([
    'can_answer',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'can-answer',
    'cannot-answer',
  ])
  @pytest.mark.asyncio
  async def test_answer_quiz_method(self, monkeypatch, common_process, can_answer):
    is_owner, owner_socket, member_socket, room = common_process
    player_ids = await self.aget_player_ids(room)

    class DummyQStat(DummyBaseQuizState):
      @database_sync_to_async
      def can_answer(self):
        return can_answer
      def update_answer(self, pk, data):
        self.answers = {pk: data}
    # Define test instance
    instance = DummyQStat(player_ids)
    # Define callbacks
    def get_callback(name):
      return instance
    def del_callback(name):
      pass

    # Define test code
    monkeypatch.setattr('quiz.consumers.g_quizstates.get_state', get_callback)
    monkeypatch.setattr('quiz.consumers.g_quizstates.del_state', del_callback)
    # Call answer_quiz method
    if is_owner:
      await owner_socket.send_json_to({'command': 'answerQuiz', 'data': 'owner-foobar'})
    else:
      await member_socket.send_json_to({'command': 'answerQuiz', 'data': 'member-foobar'})
    # Collect receive message
    owner_msg = await owner_socket.receive_nothing()
    member_msg = await member_socket.receive_nothing()
    # Create expected result
    if can_answer:
      expected_length = 1
      expected_data = 'owner-foobar' if is_owner else 'member-foobar'
      callback = lambda keys: expected_data in keys
    else:
      expected_length = 0
      callback = lambda keys: True

    assert owner_msg
    assert member_msg
    assert len(instance.answers) == expected_length
    assert callback(instance.answers.values())

  @pytest.mark.asyncio
  async def test_stop_answer_method(self, monkeypatch, common_process):
    is_owner, owner_socket, member_socket, room = common_process
    player_ids = await self.aget_player_ids(room)

    def get_callback(name):
      return DummyBaseQuizState(player_ids)
    def del_callback(name):
      pass

    # Define test code
    monkeypatch.setattr('quiz.consumers.g_quizstates.get_state', get_callback)
    monkeypatch.setattr('quiz.consumers.g_quizstates.del_state', del_callback)
    data = {'command': 'stopAnswer'}
    # Call stop_answer method
    if is_owner:
      await owner_socket.send_json_to(data)
      owner_msg = await owner_socket.receive_json_from()
      member_msg = await member_socket.receive_json_from()
      pairs = {
        'type': 'stoppedAnswering',
        'message': 'Responses have ended. No more responses will be accepted.',
      }
      callback = lambda msg: all([msg[key] == val for key, val in pairs.items()])
    else:
      await member_socket.send_json_to(data)
      owner_msg = await owner_socket.receive_nothing()
      member_msg = await member_socket.receive_nothing()
      callback = lambda msg: msg

    assert callback(owner_msg)
    assert callback(member_msg)

  @pytest.mark.asyncio
  async def test_get_answers_method(self, monkeypatch, common_process):
    is_owner, owner_socket, member_socket, room = common_process
    player_ids = await self.aget_player_ids(room)

    class DummyQStat(DummyBaseQuizState):
      @database_sync_to_async
      def get_answers(self):
        answers = {
          'owner': 'foo-bar-owner',
          'member': 'hogehoge-member',
        }
        correct_answer = 'sample'

        return answers, correct_answer

    def get_callback(name):
      return DummyQStat(player_ids)
    def del_callback(name):
      pass

    # Define test code
    monkeypatch.setattr('quiz.consumers.g_quizstates.get_state', get_callback)
    monkeypatch.setattr('quiz.consumers.g_quizstates.del_state', del_callback)
    data = {'command': 'getAnswers'}
    # Call get_answers method
    if is_owner:
      await owner_socket.send_json_to(data)
      owner_msg = await owner_socket.receive_json_from()
      member_msg = await member_socket.receive_json_from()
      def callback(msg):
        ret = all([
          msg['type'] == 'sentAnswers',
          msg['data']['owner'] == 'foo-bar-owner',
          msg['data']['member'] == 'hogehoge-member',
          msg['correctAnswer'] == 'sample',
          msg['message'] == 'All player’s answers are received.',
        ])

        return ret
    else:
      await member_socket.send_json_to(data)
      owner_msg = await owner_socket.receive_nothing()
      member_msg = await member_socket.receive_nothing()
      callback = lambda msg: msg

    assert callback(owner_msg)
    assert callback(member_msg)

  @pytest.mark.parametrize([
    'is_ended',
  ], [
    (True, ),
    (False, ),
  ], ids=[
    'is-ended',
    'is-not-ended',
  ])
  @pytest.mark.asyncio
  async def test_send_result_method(self, monkeypatch, common_process, is_ended):
    is_owner, owner_socket, member_socket, room = common_process
    player_ids = await self.aget_player_ids(room)

    class DummyQStat(DummyBaseQuizState):
      @database_sync_to_async
      def update_state(self, max_question, judgement):
        if is_ended:
          self.score.index = 5
          self.score.status = models.QuizStatusType.END
          self.score.save()
        details = {'owner': 1, 'member': 2}

        return details, is_ended

    def get_callback(name):
      instance = DummyQStat(player_ids)
      instance.update_score(room.score)

      return instance

    def del_callback(name):
      pass

    # Define test code
    monkeypatch.setattr('quiz.consumers.g_quizstates.get_state', get_callback)
    monkeypatch.setattr('quiz.consumers.g_quizstates.del_state', del_callback)
    data = {'command': 'sendResult', 'data': {}}
    # Call send_result method
    if is_owner:
      await owner_socket.send_json_to(data)
      owner_msg = await owner_socket.receive_json_from()
      member_msg = await member_socket.receive_json_from()
      # Define expected value
      if is_ended:
        message = 'All quizzes have been asked. Please press the reset button.'
        expected_index = 5
        expected_status = models.QuizStatusType.END.value
      else:
        message = 'The score is updated. Please next quiz.'
        expected_index = 3
        expected_status = models.QuizStatusType.ANSWERING.value

      def callback(msg):
        ret = all([
          msg['type'] == 'shareResult',
          msg['data']['owner'] == 1,
          msg['data']['member'] == 2,
          msg['isEnded'] == is_ended,
          msg['message'] == message,
        ])

        return ret
    else:
      await member_socket.send_json_to(data)
      owner_msg = await owner_socket.receive_nothing()
      member_msg = await member_socket.receive_nothing()
      callback = lambda msg: msg
      expected_index = 3
      expected_status = models.QuizStatusType.ANSWERING.value
    # Get score data
    score = await self.aget_score(room=room)

    assert callback(owner_msg)
    assert callback(member_msg)
    assert await self.aget_score_status(score) == expected_status
    assert await self.aget_score_index(score) == expected_index

@pytest.mark.quiz
@pytest.mark.consumer
@pytest.mark.django_db
class TestQuizState(Common):
  @pytest.mark.asyncio
  async def test_update_score(self, aget_guest, get_room_instances):
    from copy import deepcopy
    owner = await aget_guest()
    _, _, _, room = await get_room_instances(owner)
    player_ids = await self.aget_player_ids(room)
    instance = consumers.QuizState(player_ids)
    default_score = deepcopy(instance.score)
    # Call target method
    instance.update_score(await self.aget_score(room))
    updated_score = deepcopy(instance.score)
    score = await self.aget_score(room)

    assert default_score is None
    assert await self.aget_score_index(score) == 3
    assert await self.aget_score_status(score) == models.QuizStatusType.ANSWERING.value
    assert instance.quiz is None

  @pytest.mark.parametrize([
    'do_delete',  # Define whether 'foo' key is deleted or not
    'inputs',     # Define whether 'foo' key exists or not
    'expected',
  ], [
    (True,  {'hoge':  True, 'foo':  True}, {'hoge':  True, 'foo': False}),
    (True,  {'hoge': False, 'foo': False}, {'hoge': False, 'foo': False}),
    (False, {'hoge':  True, 'foo': False}, {'hoge':  True, 'foo':  True}),
    (False, {'hoge': False, 'foo':  True}, {'hoge': False, 'foo':  True}),
  ], ids=[
    'deleted-pattern',
    'no-existing-pattern',
    'override-pattern',
    'insert-pattern',
  ])
  def test_update_player(self, do_delete, inputs, expected):
    instance = consumers.QuizState(['hoge', 'foo'])
    instance.players = inputs
    # Call target method
    instance.update_player('foo', do_delete=do_delete)
    output = dict(instance.players)

    assert len(output) == len(expected)
    assert all([output[key] == val for key, val in expected.items()])

  @pytest.mark.parametrize([
    'inputs',
    'expected',
  ], [
    ({'hoge': True, 'foo': True}, True),
    ({'hoge': True, 'foo': False}, True),
    ({'hoge': False, 'foo': False}, False),
  ], ids=[
    'both-players-exist',
    'only-hoge-player-exists',
    'no-player-exists',
  ])
  def test_has_player(self, inputs, expected):
    instance = consumers.QuizState(['hoge', 'foo'])
    instance.players = inputs
    # Call target method
    output = instance.has_player()

    assert output == expected

  @pytest.mark.parametrize([
    'max_question',
    'exact_idx',
  ], [
    (1, 1),
    (5, 3),
  ], ids=[
    'index-is-greater-than-max-question',
    'index-is-less-than-max-question',
  ])
  @pytest.mark.asyncio
  async def test_get_quiz(self, aget_guest, get_room_instances, max_question, exact_idx):
    @database_sync_to_async
    def aget_question(quiz):
      return quiz.question

    owner = await aget_guest()
    _, _, _, room = await get_room_instances(owner)
    player_ids = await self.aget_player_ids(room)
    instance = consumers.QuizState(player_ids)
    instance.score = await self.aget_score(room)
    # Call target method
    sentence, index = await instance.get_quiz(max_question)
    _sequence = await self.aget_score_sequence(instance.score)
    pk = _sequence[str(exact_idx)]
    exact_quiz = await database_sync_to_async(models.Quiz.objects.get)(pk=pk)
    expected_sentence = await aget_question(exact_quiz)
    score = await self.aget_score(room)

    assert sentence == expected_sentence
    assert index == exact_idx
    assert await self.aget_score_status(score) == models.QuizStatusType.SENT_QUESTION.value
    assert await self.aget_score_index(score) == exact_idx
    assert str(instance.quiz.pk) == pk
    assert len(instance.answers) == 0

  @pytest.mark.parametrize([
    'members',
    'answered',
    'expected',
  ], [
    (['foo', 'bar'], ['foo'], False),
    (['foo', 'bar'], ['foo', 'bar'], True),
  ], ids=[
    'is-not-completed',
    'is-completed',
  ])
  def test_update_member_status(self, members, answered, expected):
    instance = consumers.QuizState(['foo', 'bar'])
    instance.answers = {}
    instance.players = {key: True for key in members}

    for pk in answered:
      is_completed = instance.update_member_status(pk)

    assert len(instance.answers) == len(answered)
    assert is_completed == expected
    assert all([val is None for val in instance.answers.values()])

  @pytest.mark.asyncio
  async def test_answering_phase(self, mocker, aget_guest, get_room_instances):
    dummy_time = datetime(2021,12,3,5,14,56)
    _format = '%Y-%m-%d %H:%M:%S'
    mocker.patch('quiz.consumers.get_current_time', return_value=dummy_time)
    owner = await aget_guest()
    _, _, _, room = await get_room_instances(owner)
    inputs = {'foo': None, 'bar': None}
    instance = consumers.QuizState(['foo', 'bar'])
    instance.players = dict(inputs)
    instance.score = await self.aget_score(room)
    # Call target method
    await instance.answering_phase()
    score = await self.aget_score(room)
    status = await self.aget_score_status(score)

    assert status == models.QuizStatusType.ANSWERING.value
    assert instance.current_time.strftime(_format) == dummy_time.strftime(_format)
    assert len(instance.answers) == len(inputs)
    assert all([all([key in inputs.keys(), item['answer'] == '', item['time'] == 0]) for key, item in instance.answers.items()])

  @pytest.mark.parametrize([
    'status',
    'is_valid',
  ], [
    (models.QuizStatusType.START,            False),
    (models.QuizStatusType.WAITING,          False),
    (models.QuizStatusType.SENT_QUESTION,    False),
    (models.QuizStatusType.ANSWERING,        True),
    (models.QuizStatusType.RECEIVED_ANSWERS, False),
    (models.QuizStatusType.JUDGING,          False),
    (models.QuizStatusType.END,              False),
  ], ids=[
    'start-phase',
    'waiting-phase',
    'sent-question-phase',
    'answering-phase',
    'received-answers-phase',
    'judging-phase',
    'end-phase',
  ])
  @pytest.mark.asyncio
  async def test_can_answer(self, aget_guest, get_room_instances, status, is_valid):
    @database_sync_to_async
    def aset_score_status(score, status):
      score.status = status
      score.save()
    # Define test code
    owner = await aget_guest()
    _, _, _, room = await get_room_instances(owner)
    inputs = {'foo': None, 'bar': None}
    instance = consumers.QuizState(['foo', 'bar'])
    score = await self.aget_score(room)
    await aset_score_status(score, status)
    instance.score = await self.aget_score(room)
    # Call target method
    output = await instance.can_answer()

    assert output == is_valid

  def test_update_answer(self, mocker):
    _format = '%Y-%m-%d %H:%M:%S'
    mocker.patch('quiz.consumers.get_current_time', side_effect=[datetime(2021,12,3,5,14,45), datetime(2021,12,3,5,14,53), datetime(2021,12,3,5,14,57)])
    instance = consumers.QuizState(['foo', 'bar'])
    instance.current_time = datetime(2021,12,3,5,14,50)
    # Call target method
    instance.update_answer('foo', 'hoge')
    instance.update_answer('bar', 'hogehoge')
    foo_answer = instance.answers['foo']
    bar_answer = instance.answers['bar']

    assert foo_answer['answer'] == 'hoge'
    assert bar_answer['answer'] == 'hogehoge'
    assert int(foo_answer['time']) == 3
    assert int(bar_answer['time']) == 7

  @pytest.mark.asyncio
  async def test_received_all_answers_phase(self, aget_guest, get_room_instances):
    owner = await aget_guest()
    _, _, _, room = await get_room_instances(owner)
    player_ids = await self.aget_player_ids(room)
    instance = consumers.QuizState(player_ids)
    instance.score = await self.aget_score(room)
    # Call target method
    await instance.received_all_answers_phase()
    score = await self.aget_score(room)

    assert await self.aget_score_status(score) == models.QuizStatusType.RECEIVED_ANSWERS.value

  @pytest.mark.asyncio
  async def test_get_answers(self, aget_guest, get_room_instances):
    @database_sync_to_async
    def _aget_answer(quiz):
      return quiz.answer
    # Define test cose
    owner = await aget_guest()
    _, _, _, room = await get_room_instances(owner)
    inputs = {
      'foo': {
        'answer': 'hoge123',
        'time': 3.0,
      },
      'bar': {
        'answer': 'hogehoge-321',
        'time': 5.0,
      }
    }
    instance = consumers.QuizState(['foo', 'bar'])
    instance.answers = dict(inputs)
    instance.score = await self.aget_score(room)
    _sequence = await self.aget_score_sequence(instance.score)
    instance.quiz = await database_sync_to_async(models.Quiz.objects.get)(pk=_sequence['1'])
    # Call target method
    player_answers, correct_answer = await instance.get_answers()
    score = await self.aget_score(room)
    foo_answer = player_answers['foo']
    bar_answer = player_answers['bar']

    assert await self.aget_score_status(score) == models.QuizStatusType.JUDGING.value
    assert all([foo_answer['answer'] == 'hoge123', abs(foo_answer['time'] - 3) < 1e-5])
    assert all([bar_answer['answer'] == 'hogehoge-321', abs(bar_answer['time'] - 5) < 1e-5])
    assert correct_answer == await _aget_answer(instance.quiz)

  @pytest.fixture(params=['first-question', 'second-question', 'last-question'])
  def get_quiz_status_patterns(self, request):
    max_question = 3

    if request.param == 'first-question':
      data = {
        'index': 1,
        'detail': {'foo': 0, 'bar': 0},
      }
      judgement = {'foo': 0, 'bar': 1}
      expected = {
        'output': {'foo': 0, 'bar': 1},
        'status': models.QuizStatusType.WAITING.value,
        'index': 2,
        'is_ended': False,
      }
    elif request.param == 'second-question':
      data = {
        'index': 2,
        'detail': {'foo': 0, 'bar': 1},
      }
      judgement = {'foo': 1, 'bar': 1}
      expected = {
        'output': {'foo': 1, 'bar': 2},
        'status': models.QuizStatusType.WAITING.value,
        'index': 3,
        'is_ended': False,
      }
    else:
      data = {
        'index': 3,
        'detail': {'foo': 1, 'bar': 2},
      }
      judgement = {'foo': 3, 'bar': 1}
      expected = {
        'output': {'foo': 4, 'bar': 3},
        'status': models.QuizStatusType.END.value,
        'index': 4,
        'is_ended': True,
      }

    return data, judgement, expected, max_question

  @pytest.mark.asyncio
  async def test_update_state(self, aget_guest, get_room_instances, get_quiz_status_patterns):
    @database_sync_to_async
    def aset_score(score, data):
      score.index = data['index']
      score.detail = data['detail']
      score.save()
    # Define test cose
    owner = await aget_guest()
    _, _, _, room = await get_room_instances(owner)
    data, judgement, expected, max_question = get_quiz_status_patterns
    await aset_score(await self.aget_score(room), data)
    instance = consumers.QuizState(['foo', 'bar'])
    instance.score = await self.aget_score(room)
    instance.quiz = 3
    # Call target method
    detail, is_ended = await instance.update_state(max_question, judgement)
    score = await self.aget_score(room)
    db_detail = await self.aget_score_detail(score)

    assert is_ended == expected['is_ended']
    assert instance.quiz is None
    assert all([detail[key] == val for key, val in expected['output'].items()])
    assert all([str(db_detail[key]) == str(val) for key, val in expected['output'].items()])
    assert await self.aget_score_status(score) == expected['status']
    assert await self.aget_score_index(score) == expected['index']

@pytest.mark.quiz
@pytest.mark.consumer
class TestConsumerState:
  def test_init(self):
    instance = consumers.ConsumerState()

    assert len(instance.states) == 0

  def test_get_state(self):
    instance = consumers.ConsumerState()
    output = instance.get_state('hoge')

    assert output is None

  def test_get_state_with_data(self):
    instance = consumers.ConsumerState()
    instance.states['hoge'] = consumers.QuizState(['x-user', 'y-user'])
    output = instance.get_state('hoge')

    assert isinstance(output, consumers.QuizState)

  def test_set_state(self):
    instance = consumers.ConsumerState()
    instance.set_state('hoge', consumers.QuizState(['x-user', 'y-user']))

    assert isinstance(instance.states['hoge'], consumers.QuizState)

  @pytest.mark.parametrize([
    'name',
    'keys',
  ], [
    ('hoge', []),
    ('foo', ['hoge']),
  ], ids=[
    'can-delete',
    'cannot-delete',
  ])
  def test_del_state(self, name, keys):
    instance = consumers.ConsumerState()
    instance.states['hoge'] = consumers.QuizState(['x-user', 'y-user'])
    instance.del_state(name)

    assert len(instance.states) == len(keys)
    assert all(isinstance(instance.states[key], consumers.QuizState) for key in keys)