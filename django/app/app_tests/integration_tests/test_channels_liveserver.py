import pytest
import asyncio
import time
# Libraries to define channels_live_server
import functools
import threading
from io import BytesIO
from channels.db import database_sync_to_async
from channels.routing import get_default_application
from daphne.testing import DaphneProcess
from daphne.server import Server as DaphneServer
from daphne.endpoints import build_endpoint_description_strings
from django.core.exceptions import ImproperlyConfigured
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.db import connections
from django.http import SimpleCookie
from django.test.utils import modify_settings
from django.test.client import ClientMixin
# For test
import websockets
import json
from contextlib import AsyncExitStack
from app_tests import factories
from account.models import RoleType
from quiz import models

def get_open_port():
  import socket
  _sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  _sock.bind(('', 0))
  _sock.listen(1)
  _, port = _sock.getsockname()
  _sock.close()

  return port

def make_application(*, static_wrapper):
  # Module-level function for pickle-ability
  application = get_default_application()

  if static_wrapper is not None:
    application = static_wrapper(application)

  return application

class ChannelsLiveServer(ClientMixin):
  host = 'localhost'
  static_wrapper = ASGIStaticFilesHandler
  serve_static = True

  def __init__(self, port=None):
    self.json_encoder = DjangoJSONEncoder
    self.cookies = SimpleCookie()
    self.errors = BytesIO()
    self.port = port or get_open_port()

    for connection in connections.all():
      if connection.vendor == 'sqlite' and connection.is_in_memory_db() and len(connection.settings_dict.get('TEST', {})) == 0:
        raise ImproperlyConfigured('ChannelsLiveServer can not be used with in memory databases')

      self._live_server_modified_settings = modify_settings(ALLOWED_HOSTS={'append': self.host})
      self._live_server_modified_settings.enable()
      get_application = functools.partial(
        make_application,
        static_wrapper=self.static_wrapper if self.serve_static else None,
      )
      endpoints = build_endpoint_description_strings(host=self.host, port=self.port)
      self._server = DaphneServer(application=get_application(), endpoints=endpoints)
      thread = threading.Thread(target=self._server.run)
      thread.start()
      # Wait until DaphneServer starts
      while not self._server.listening_addresses:
        time.sleep(0.1)

  def stop(self) -> None:
    self._server.stop()
    self._live_server_modified_settings.disable()

  def get_headers(self):
    vals = [f'{morsel.key}={morsel.coded_value}' for morsel in self.cookies.values()]
    header = {
      'Cookie': '; '.join(vals),
      'Origin': self.http,
    }

    return header

  @property
  def ws(self):
    return f'ws://{self.host}:{self.port}'

  @property
  def http(self):
    return f'http://{self.host}:{self.port}'

@pytest.fixture(scope='module')
def get_room_info(django_db_blocker):
  @database_sync_to_async
  def inner():
    with django_db_blocker.unblock():
      owner = factories.UserFactory(is_active=True, role=RoleType.GUEST, screen_name='guest-owner')
      genres = list(factories.GenreFactory.create_batch(3, is_enabled=True))
      creators = list(factories.UserFactory.create_batch(3, is_active=True, role=RoleType.GUEST))
      guests = list(factories.UserFactory.create_batch(4, is_active=True, role=RoleType.GUEST))
      # Update screen name
      for idx, creator in enumerate(creators):
        creator.screen_name = f'creator{idx}'
        creator.save()
      for idx, guest in enumerate(guests):
        guest.screen_name = f'guest{idx}'
        guest.save()
      # Note: only creators[2] and guests[3] are members
      members = [creators[2], guests[3]]
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

    return owner, creators, guests, room

  return inner

class Common:
  pk_convertor = lambda _self, xs: [item.pk for item in xs]

  @database_sync_to_async
  def aget_quiz(self, pk):
    return models.Quiz.objects.get(pk=pk)

  @database_sync_to_async
  def aget_quiz_question(self, quiz):
    return quiz.question

  @database_sync_to_async
  def aget_quiz_answer(self, quiz):
    return quiz.answer

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

  @pytest.fixture(scope='session')
  def channels_live_server(self, request):
    server = ChannelsLiveServer()
    request.addfinalizer(server.stop)

    return server

@pytest.mark.webtest
@pytest.mark.django_db
class TestQuizRoomWithLiveServer(Common):
  room_url = lambda _self, server, room: f'{server.ws}/ws/quizroom/{room.pk}'

  @pytest.mark.parametrize([
    'user_type',
  ], [
    ('owner', ),
    ('creator', ),
    ('guest', ),
  ], ids=lambda xs: str(xs))
  @pytest.mark.asyncio
  async def test_connect_websocket(self, get_room_info, channels_live_server, user_type):
    owner, creators, guests, room = await get_room_info()
    url = self.room_url(channels_live_server, room)
    # Login
    patterns = {
      'owner': owner,
      'creator': creators[2],
      'guest': guests[3],
    }
    user = patterns[user_type]
    await channels_live_server.aforce_login(user)
    headers = channels_live_server.get_headers()
    # Connect quiz room
    async with websockets.connect(url, additional_headers=headers) as ws:
      response = json.loads(await ws.recv())

    assert response['message'] == f'Join {user} to {room.name}'

  @pytest.mark.asyncio
  async def test_cannot_connect_websocket(self, get_room_info, channels_live_server):
    from websockets.exceptions import InvalidMessage
    _, creators, _, room = await get_room_info()
    url = self.room_url(channels_live_server, room)
    user = creators[1]
    await channels_live_server.aforce_login(user)
    headers = channels_live_server.get_headers()
    # Connect quiz room
    with pytest.raises(InvalidMessage) as ex:
      async with websockets.connect(url, additional_headers=headers) as ws:
        pass

    assert 'did not receive a valid HTTP response' in ex.value.args[0]

  async def remove_all_messages(self, ws_users):
    for ws_conn in ws_users.values():
      msg_exists = True
      # Call recv method
      while msg_exists:
        try:
          await asyncio.wait_for(ws_conn.recv(), timeout=0.1)
        except TimeoutError:
          msg_exists = False

  @pytest.fixture
  def exec_common_connect_process(self, get_room_info, channels_live_server):
    async def inner(acallback, apreproess=None):
      owner, creators, guests, room = await get_room_info()
      url = self.room_url(channels_live_server, room)
      # Execute pre-process
      if apreproess is not None and callable(apreproess):
        await apreproess(room)

      async with AsyncExitStack() as astack:
        pairs = {'owner': owner, 'creator': creators[2], 'guest': guests[3]}
        ws_users = {}
        user_pks = {}
        # Create connection for each user
        for key, user in pairs.items():
          await channels_live_server.aforce_login(user)
          headers = channels_live_server.get_headers()
          ws_users[key] = await astack.enter_async_context(websockets.connect(url, additional_headers=headers))
          user_pks[key] = str(user.pk)
        # Delete old message
        await self.remove_all_messages(ws_users)
        # Call callback function
        responses = await acallback(ws_users=ws_users, user_pks=user_pks, room=room, server=channels_live_server)

      return responses

    return inner

  @pytest.mark.asyncio
  async def test_reset_quiz_command(self, exec_common_connect_process):
    async def acallback(ws_users, room, **kwargs):
      # Send message
      await ws_users['owner'].send(json.dumps({'command': 'resetQuiz'}))
      # Call recv method
      try:
        res_owner = json.loads(await asyncio.wait_for(ws_users['owner'].recv(), timeout=0.5))
        res_creator = json.loads(await asyncio.wait_for(ws_users['creator'].recv(), timeout=0.5))
        res_guest = json.loads(await asyncio.wait_for(ws_users['guest'].recv(), timeout=0.5))
        responses = [res_owner, res_creator, res_guest]
      except TimeoutError as ex:
        pytest.fail(f'Unexpected Error: {ex}')

      return responses, room
    # Get result
    responses, room = await exec_common_connect_process(acallback)
    score = await self.aget_score(room)
    status = await self.aget_score_status(score)

    assert status == models.QuizStatusType.START.value
    assert all([res['type'] == 'resetCompleted' for res in responses])
    assert all([res['message'] == 'Status reset is completed' for res in responses])

  @pytest.mark.asyncio
  async def test_get_next_quiz_command(self, exec_common_connect_process):
    async def acallback(ws_users, room, **kwargs):
      await database_sync_to_async(room.reset)()
      # Send message
      await ws_users['owner'].send(json.dumps({'command': 'getNextQuiz'}))
      # Call recv method
      try:
        res_owner = json.loads(await asyncio.wait_for(ws_users['owner'].recv(), timeout=0.5))
        res_creator = json.loads(await asyncio.wait_for(ws_users['creator'].recv(), timeout=0.5))
        res_guest = json.loads(await asyncio.wait_for(ws_users['guest'].recv(), timeout=0.5))
        responses = [res_owner, res_creator, res_guest]
      except TimeoutError as ex:
        pytest.fail(f'Unexpected Error: {ex}')

      return responses, room
    # Get result
    responses, room = await exec_common_connect_process(acallback)
    score = await self.aget_score(room)
    status = await self.aget_score_status(score)
    idx = await self.aget_score_index(score)
    seq = await self.aget_score_sequence(score)
    quiz = await self.aget_quiz(seq[str(idx)])
    question = await self.aget_quiz_question(quiz)

    assert status == models.QuizStatusType.SENT_QUESTION.value
    assert all([res['type'] == 'sentNextQuiz' for res in responses])
    assert all([res['message'] == 'The next quiz is received.' for res in responses])
    assert all([res['data'] == question for res in responses])
    assert all([res['index'] == idx for res in responses])

  @pytest.mark.asyncio
  async def test_received_quiz_command_with_all_responses(self, exec_common_connect_process):
    async def acallback(ws_users, **kwargs):
      # Send message
      msg = json.dumps({'command': 'receivedQuiz'})
      await ws_users['owner'].send(msg)
      await ws_users['creator'].send(msg)
      await ws_users['guest'].send(msg)
      # Call recv method
      try:
        res_owner = json.loads(await asyncio.wait_for(ws_users['owner'].recv(), timeout=0.5))
        res_creator = json.loads(await asyncio.wait_for(ws_users['creator'].recv(), timeout=0.5))
        res_guest = json.loads(await asyncio.wait_for(ws_users['guest'].recv(), timeout=0.5))
        responses = [res_owner, res_creator, res_guest]
      except TimeoutError as ex:
        pytest.fail(f'Unexpected Error: {ex}')

      return responses
    # Get result
    responses = await exec_common_connect_process(acallback)

    assert all([res['type'] == 'sentAllQuizzes' for res in responses])
    assert all([res['message'] == 'All players received the quiz.' for res in responses])

  @pytest.mark.asyncio
  async def test_received_quiz_command_without_all_responses(self, exec_common_connect_process):
    async def acallback(ws_users, **kwargs):
      # Send message
      await ws_users['guest'].send(json.dumps({'command': 'receivedQuiz'}))
      # Receive message
      with pytest.raises(TimeoutError) as ex:
        _ = await asyncio.wait_for(ws_users['owner'].recv(), timeout=1.0)

      return str(ex)
    # Get result
    err_msg = await exec_common_connect_process(acallback)

    assert 'TimeoutError' in err_msg

  @pytest.mark.asyncio
  async def test_start_answer_command(self, exec_common_connect_process):
    async def acallback(ws_users, room, **kwargs):
      # Send message
      await ws_users['owner'].send(json.dumps({'command': 'startAnswer'}))
      # Call recv method
      try:
        res_owner = json.loads(await asyncio.wait_for(ws_users['owner'].recv(), timeout=0.5))
        res_creator = json.loads(await asyncio.wait_for(ws_users['creator'].recv(), timeout=0.5))
        res_guest = json.loads(await asyncio.wait_for(ws_users['guest'].recv(), timeout=0.5))
        responses = [res_owner, res_creator, res_guest]
      except TimeoutError as ex:
        pytest.fail(f'Unexpected Error: {ex}')

      return responses, room
    # Get result
    responses, room = await exec_common_connect_process(acallback)
    score = await self.aget_score(room)
    status = await self.aget_score_status(score)

    assert status == models.QuizStatusType.ANSWERING.value
    assert all([res['type'] == 'startedAnswering' for res in responses])

  @pytest.mark.asyncio
  async def test_stop_answer_command(self, exec_common_connect_process):
    async def acallback(ws_users, room, **kwargs):
      # Send message
      await ws_users['owner'].send(json.dumps({'command': 'stopAnswer'}))
      # Call recv method
      try:
        res_owner = json.loads(await asyncio.wait_for(ws_users['owner'].recv(), timeout=0.5))
        res_creator = json.loads(await asyncio.wait_for(ws_users['creator'].recv(), timeout=0.5))
        res_guest = json.loads(await asyncio.wait_for(ws_users['guest'].recv(), timeout=0.5))
        responses = [res_owner, res_creator, res_guest]
      except TimeoutError as ex:
        pytest.fail(f'Unexpected Error: {ex}')

      return responses, room
    # Get result
    responses, room = await exec_common_connect_process(acallback)
    score = await self.aget_score(room)
    status = await self.aget_score_status(score)

    assert status == models.QuizStatusType.RECEIVED_ANSWERS.value
    assert all([res['type'] == 'stoppedAnswering' for res in responses])
    assert all([res['message'] == 'Responses have ended. No more responses will be accepted.' for res in responses])

  @pytest.mark.asyncio
  async def test_get_answers_command(self, exec_common_connect_process):
    async def acallback(ws_users, room, **kwargs):
      await database_sync_to_async(room.reset)()
      # Send message
      await ws_users['owner'].send(json.dumps({'command': 'getNextQuiz'}))
      await self.remove_all_messages(ws_users)
      await ws_users['owner'].send(json.dumps({'command': 'getAnswers'}))
      # Call recv method
      try:
        res_owner = json.loads(await asyncio.wait_for(ws_users['owner'].recv(), timeout=0.5))
        res_creator = json.loads(await asyncio.wait_for(ws_users['creator'].recv(), timeout=0.5))
        res_guest = json.loads(await asyncio.wait_for(ws_users['guest'].recv(), timeout=0.5))
        responses = [res_owner, res_creator, res_guest]
      except TimeoutError as ex:
        pytest.fail(f'Unexpected Error: {ex}')

      return responses, room
    # Get result
    responses, room = await exec_common_connect_process(acallback)
    score = await self.aget_score(room)
    status = await self.aget_score_status(score)
    idx = await self.aget_score_index(score)
    seq = await self.aget_score_sequence(score)
    quiz = await self.aget_quiz(seq[str(idx)])
    answer = await self.aget_quiz_answer(quiz)

    assert status == models.QuizStatusType.JUDGING.value
    assert all([res['type'] == 'sentAnswers' for res in responses])
    assert all([res['message'] == 'All player’s answers are received.' for res in responses])
    assert all([res['correctAnswer'] == answer for res in responses])
    assert all([isinstance(res['data'], dict) for res in responses])

  @pytest.mark.parametrize([
    'max_question',
    'is_ended',
    'stat_type',
    'out_msg',
  ], [
    (5, False, models.QuizStatusType.WAITING.value, 'The score is updated. Please next quiz.'),
    (1, True, models.QuizStatusType.END.value, 'All quizzes have been asked. Please press the reset button.'),
  ], ids=[
    'is-not-ended',
    'is-ended',
  ])
  @pytest.mark.asyncio
  async def test_send_result_command(self, exec_common_connect_process, max_question, is_ended, stat_type, out_msg):
    @database_sync_to_async
    def apreproess(room):
      room.reset()
      room.score.index = 2
      room.score.save()
      room.max_question = max_question
      room.save()

    async def acallback(ws_users, room, user_pks, **kwargs):
      # Send message
      data = {
        user_pks['owner']: 2,
        user_pks['creator']: 3,
        user_pks['guest']: 1,
      }
      await ws_users['owner'].send(json.dumps({'command': 'sendResult', 'data': data}))
      # Call recv method
      try:
        res_owner = json.loads(await asyncio.wait_for(ws_users['owner'].recv(), timeout=0.3))
        res_creator = json.loads(await asyncio.wait_for(ws_users['creator'].recv(), timeout=0.3))
        res_guest = json.loads(await asyncio.wait_for(ws_users['guest'].recv(), timeout=0.3))
        responses = [res_owner, res_creator, res_guest]
      except TimeoutError as ex:
        pytest.fail(f'Unexpected Error: {ex}')

      return responses, room
    # Get result
    responses, room = await exec_common_connect_process(acallback, apreproess=apreproess)
    score = await self.aget_score(room)
    status = await self.aget_score_status(score)
    detail = await self.aget_score_detail(score)

    assert status == stat_type
    assert all([res['type'] == 'shareResult' for res in responses])
    assert all([res['message'] == out_msg for res in responses])
    assert all([res['isEnded'] == is_ended for res in responses])
    assert all([all([res['data'][key] == val for key, val in detail.items()]) for res in responses])

  # ================
  # Invalid patterns
  # ================
  @pytest.fixture(params=['creator', 'guest'])
  def get_room_member(self, request):
    yield request.param

  @pytest.mark.parametrize([
    'command',
    'data',
  ], [
    ('resetQuiz', None),
    ('getNextQuiz', None),
    ('startAnswer', None),
    ('stopAnswer', None),
    ('getAnswers', None),
    ('sendResult', {'hoge': 2, 'foo': 3}),
  ], ids=[
    'rest-quiz',
    'get-next-quiz',
    'start-answer',
    'stop-answer',
    'get-answers',
    'send-result',
  ])
  @pytest.mark.asyncio
  async def test_invalid_commands(self, exec_common_connect_process, get_room_member, command, data):
    user_type = get_room_member
    @database_sync_to_async
    def apreproess(room):
      room.reset()

    async def acallback(ws_users, **kwargs):
      # Send message
      await ws_users[user_type].send(json.dumps({'command': command, 'data': data}))
      # Receive message
      with pytest.raises(TimeoutError) as ex:
        _ = await asyncio.wait_for(ws_users['owner'].recv(), timeout=1.0)

      return str(ex)
    # Get result
    err_msg = await exec_common_connect_process(acallback, apreproess=apreproess)

    assert 'TimeoutError' in err_msg

  # ============================
  # Check a series of processing
  # ============================
  @pytest.mark.asyncio
  async def test_check_a_seires_of_processing(self, get_room_info, channels_live_server):
    @database_sync_to_async
    def get_max_question(room):
      return room.max_question
    # Definetest code
    owner, creators, guests, room = await get_room_info()
    await database_sync_to_async(room.reset)()
    url = self.room_url(channels_live_server, room)
    all_answers = []
    all_details = []
    all_statuses = []
    max_question = await get_max_question(room)

    # Start Quiz game
    async with AsyncExitStack() as astack:
      pairs = {'owner': owner, 'creator': creators[2], 'guest': guests[3]}
      ws_users = {}
      user_pks = {}

      # Step1: Connect websocket for all members
      for key, user in pairs.items():
        await channels_live_server.aforce_login(user)
        headers = channels_live_server.get_headers()
        ws_users[key] = await astack.enter_async_context(websockets.connect(url, additional_headers=headers))
        user_pks[key] = str(user.pk)
      await self.remove_all_messages(ws_users)

      for loop_count in range(max_question):
        # Step2: Get next quiz and reply
        await ws_users['owner'].send(json.dumps({'command': 'getNextQuiz'}))
        time.sleep(0.3)
        await self.remove_all_messages(ws_users)
        for key, ws_conn in ws_users.items():
          await ws_conn.send(json.dumps({'command': 'receivedQuiz'}))
        time.sleep(0.3)
        await self.remove_all_messages(ws_users)

        # Step3: Start answer
        await ws_users['owner'].send(json.dumps({'command': 'startAnswer'}))
        time.sleep(0.2)
        await self.remove_all_messages(ws_users)

        # Step4: Each member answers quiz
        delay = loop_count / 10.0
        await ws_users['owner'].send(json.dumps({'command': 'answerQuiz', 'data': f'hoge-owner{loop_count}'}))
        time.sleep(0.1 + delay)
        await ws_users['creator'].send(json.dumps({'command': 'answerQuiz', 'data': f'foo-creator{loop_count}'}))
        time.sleep(0.2 + delay)
        await ws_users['guest'].send(json.dumps({'command': 'answerQuiz', 'data': f'bar-guest{loop_count}'}))

        # Step5: Stop answer
        await ws_users['owner'].send(json.dumps({'command': 'stopAnswer'}))
        time.sleep(0.3)
        await self.remove_all_messages(ws_users)

        # Step6: Get answers
        await ws_users['owner'].send(json.dumps({'command': 'getAnswers'}))
        message = json.loads(await asyncio.wait_for(ws_users['owner'].recv(), timeout=1.0))
        all_answers += [message['data']]
        await self.remove_all_messages(ws_users)

        # Step7: Send result
        current_scores = {
          user_pks['owner']: loop_count + 3,
          user_pks['creator']: loop_count + 2,
          user_pks['guest']: loop_count + 1,
        }
        await ws_users['owner'].send(json.dumps({'command': 'sendResult', 'data': current_scores}))
        time.sleep(0.3)
        await self.remove_all_messages(ws_users)
        score = await self.aget_score(room)
        detail = await self.aget_score_detail(score)
        status = await self.aget_score_status(score)
        all_details += [detail]
        all_statuses += [status]

    # Create expected values
    expected_answers = []
    expected_details = []
    expected_statuses = []
    o_pk, c_pk, g_pk = user_pks['owner'], user_pks['creator'], user_pks['guest']
    o_nm, c_nm, g_nm = f'user{o_pk}', f'user{c_pk}', f'user{g_pk}'
    details = {o_pk: 0, c_pk: 0, g_pk: 0}
    for idx in range(max_question):
      delay = idx / 10.0
      # Answer
      answers = {
        o_nm: {'answer': f'hoge-owner{idx}',  'min-time': 0.2,           'max-time': 0.55},
        c_nm: {'answer': f'foo-creator{idx}', 'min-time': 0.3 + 1*delay, 'max-time': 0.65 + 1*delay},
        g_nm: {'answer': f'bar-guest{idx}',   'min-time': 0.5 + 2*delay, 'max-time': 0.85 + 2*delay},
      }
      expected_answers += [answers]
      # Detail
      details = {
        o_pk: details[o_pk] + idx + 3,
        c_pk: details[c_pk] + idx + 2,
        g_pk: details[g_pk] + idx + 1,
      }
      expected_details += [details]
      # Status
      if (idx + 1) < max_question:
        expected_statuses += [models.QuizStatusType.WAITING.value]
      else:
        expected_statuses += [models.QuizStatusType.END.value]

    assert len(all_answers) == len(expected_answers)
    assert len(all_details) == len(expected_details)
    assert len(all_statuses) == len(expected_statuses)
    # For status
    assert all([estimated == exact for estimated, exact in zip(all_statuses, expected_statuses)])
    # For owner data
    assert all([
      all([estimated[o_nm]['answer'] == exact[o_nm]['answer']])
      for estimated, exact in zip(all_answers, expected_answers)
    ])
    assert all([
      all([exact[o_nm]['min-time'] < estimated[o_nm]['time'] < exact[o_nm]['max-time']])
      for estimated, exact in zip(all_answers, expected_answers)
    ])
    assert all([
      all([estimated[o_pk] == exact[o_pk]])
      for estimated, exact in zip(all_details, expected_details)
    ])
    # For creator
    assert all([
      all([estimated[c_nm]['answer'] == exact[c_nm]['answer']])
      for estimated, exact in zip(all_answers, expected_answers)
    ])
    assert all([
      all([exact[c_nm]['min-time'] < estimated[c_nm]['time'] < exact[c_nm]['max-time']])
      for estimated, exact in zip(all_answers, expected_answers)
    ])
    assert all([
      all([estimated[c_pk] == exact[c_pk]])
      for estimated, exact in zip(all_details, expected_details)
    ])
    # For guest
    assert all([
      all([estimated[g_nm]['answer'] == exact[g_nm]['answer']])
      for estimated, exact in zip(all_answers, expected_answers)
    ])
    assert all([
      all([exact[g_nm]['min-time'] < estimated[g_nm]['time'] < exact[g_nm]['max-time']])
      for estimated, exact in zip(all_answers, expected_answers)
    ])
    assert all([
      all([estimated[g_pk] == exact[g_pk]])
      for estimated, exact in zip(all_details, expected_details)
    ])