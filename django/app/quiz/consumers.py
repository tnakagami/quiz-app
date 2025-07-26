from logging import getLogger
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils.translation import gettext_lazy
from utils.models import get_current_time, convert_timezone
from . import models

QuizStatusType = models.QuizStatusType

class QuizState:
  ##
  # @brief Constructor of QuizState
  def __init__(self):
    self.score = None
    self.quiz = None
    self.players = {}
    self.answers = {}
    self.current_time = get_current_time()

  ##
  # @brief Update score
  # @param score Instance of score
  def update_score(self, score):
    self.score = score
    self.quiz = None

  ##
  # @brief Update player list
  # @param pk Player's primary key
  # @param do_delete Delete target player from player list if true (Default: False)
  def update_player(self, pk, do_delete=False):
    if do_delete and self.players.get(pk, False):
      del self.players[pk]
    elif not do_delete:
      self.players[pk] = True

  ##
  # @brief Check rest players
  # @return Judgement result
  # @retval True  Some players exist
  # @retval False There is no player in this room
  def has_player(self):
    return len(self.players) > 0

  # ===================
  # = Playing process =
  # ===================
  ##
  # @brief Get next quiz
  # @param max_question The number of maximum quizzes
  # @return sentence Quiz sentence
  # @return index The current index of quiz
  @database_sync_to_async
  def get_quiz(self, max_question):
    index = self.score.index
    self.answers = {}

    if index > max_question:
      index = 1
    pk = self.score.sequence.get(str(index))
    self.quiz = models.Quiz.objects.get(pk=pk)
    sentence = self.quiz.question
    # Update records
    self.score.status = QuizStatusType.SENT_QUESTION
    self.score.save()

    return sentence, index

  ##
  # @brief Update player list of revceived quiz
  # @param pk The request user's primary key
  # @return is_completed Descrive whether the system sent quiz to all players or not
  def update_member_status(self, pk):
    self.answers[pk] = None
    is_completed = len(self.answers) >= len(self.players)

    return is_completed

  ##
  # @brief Change answering phase
  @database_sync_to_async
  def answering_phase(self):
    self.answers = dict([(key, {'answer': '', 'time': 0}) for key in self.players.keys()])
    self.score.status = QuizStatusType.ANSWERING
    self.score.save()
    self.current_time = get_current_time()

  ##
  # @brief Check whether hte members can answer quiz or not
  # @return Judgement result
  # @retval True  The members can answer quiz
  # @retval False The members cannot answer quiz
  @database_sync_to_async
  def can_answer(self):
    is_valid = self.score.status == QuizStatusType.ANSWERING

    return is_valid

  ##
  # @brief Change answering phase
  # @param pk The request user's primary key
  # @param answer The request user's answer
  def update_answer(self, pk, answer):
    elapsed_time = get_current_time() - self.current_time
    self.answers[pk] = {
      'answer': answer,
      'time': elapsed_time.total_seconds(),
    }

  ##
  # @brief Change received all answers phase
  @database_sync_to_async
  def received_all_answers_phase(self):
    self.score.status = QuizStatusType.RECEIVED_ANSWERS
    self.score.save()

  ##
  # @brief Collect correct answer and player's answers
  # @return player_answers The player's answers
  # @return correct_answer The correct answer
  @database_sync_to_async
  def get_answers(self):
    self.score.status = QuizStatusType.JUDGING
    self.score.save()
    player_answers = dict(self.answers)
    correct_answer = self.quiz.answer

    return player_answers, correct_answer

  ##
  # @breif Update scores for each player
  # @param max_question The number of maximum quizzes
  # @param judgement Judgement result for player's answer
  # @return detail The updated score of each player
  # @return is_enabled Judgement result of whether all quizzes have been asked or not.
  @database_sync_to_async
  def update_state(self, max_question, judgement):
    index = self.score.index
    detail = self.score.detail
    # Update status
    for name, additional_count in judgement.items():
      value = detail[name]
      detail[name] = int(value) + additional_count
    self.score.detail = dict(detail)
    # Update status if needed
    if index >= max_question:
      self.score.status = QuizStatusType.END
      is_enabled = True
    else:
      self.score.status = QuizStatusType.WAITING
      is_enabled = False
    self.score.index = index + 1
    # Save record
    self.score.save()
    self.quiz = None

    return detail, is_enabled

class ConsumerState:
  ##
  # @brief Constructor of ConsumerState
  def __init__(self):
    self.states = {}

  ##
  # @brief Get target state based on given name
  # @param name Target instance name
  # @return Instance of QuizState
  def get_state(self, name):
    return self.states.get(name)

  ##
  # @brief Set QuizState's instance based on given name
  # @param name Target instance name
  # @param instance Target QuizState's instance
  def set_state(self, name, instance):
    self.states[name] = instance

  ##
  # @brief Delete QuizState's instance based on given name
  # @param name Target instance name
  def del_state(self, name):
    if name in self.states.keys():
      del self.states[name]

g_quizstates = ConsumerState()

# ================
# = QuizConsumer =
# ================
class QuizConsumer(AsyncJsonWebsocketConsumer):
  ##
  # @brief Constructor of QuizConsumer
  # @param args Positional arguments
  # @param kwargs Named arguments
  def __init__(self, *args, **kwargs):
    self.room = None
    self.group_name = None
    self.prefix = 'quiz'
    self.logger = getLogger(__name__)
    self.now = lambda: convert_timezone(get_current_time(), is_string=True, strformat='Y-m-d H:i:s')
    super().__init__(*args, **kwargs)

  ##
  # @brief Get client key
  # @param user Request user
  # @return primary key
  def get_client_key(self, user):
    return f'user{user.pk}'

  ##
  # @brief Check whether the request user is owner or not
  # @param user Request user
  # @return bool Judmgement result
  # @retval True  The request user is owner
  # @retval False The request user is not owner
  @database_sync_to_async
  def is_owner(self, user):
    return self.room.is_owner(user)

  ##
  # @brief Get room's score
  # @return The instance of room's score
  @database_sync_to_async
  def get_score(self):
    return self.room.score

  ##
  # @brief Get room's score
  # @return The number of maximum quizzes
  @database_sync_to_async
  def get_max_question(self):
    return self.room.max_question

  ##
  # @brief Connection process
  async def connect(self):
    try:
      # Get accessed user and room primary key
      user = self.scope['user']
      pk = self.scope['url_route']['kwargs']['pk']
      self.group_name = f'{self.prefix}-{pk}'
      self.room = await database_sync_to_async(models.QuizRoom.objects.get)(pk=pk)
      is_assigned = await database_sync_to_async(self.room.is_assigned)(user)
      # In the case of that request user can access the room
      if is_assigned:
        await self.accept()
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.post_accept(user)
    except Exception as ex:
      self.logger.error(f'[{self.group_name}]Connect: {ex}')

  ##
  # @brief Conduct post-accept process
  # @param user Request user
  async def post_accept(self, user):
    target = g_quizstates.get_state(self.group_name)

    if target is None:
      score = await self.get_score()
      target = QuizState()
      target.update_score(score)
      # Update status
      g_quizstates.set_state(self.group_name, target)
    # Add user data to player list
    target.update_player(self.get_client_key(user))
    # Send system message
    message = gettext_lazy('Join {name} to {room}').format(name=str(user), room=self.room.name)
    await self.channel_layer.group_send(
      self.group_name, {
        'type': 'send_group_message',
        'msg_type': 'system',
        'ids': ['message'],
        'message': message,
      }
    )

  ##
  # @brief Disconnection process
  # @param close_code status code as closing the connection
  async def disconnect(self, close_code):
    user = self.scope['user']
    await self.pre_disconnect(user)
    await self.channel_layer.group_discard(self.group_name, self.channel_name)
    await self.close()
    await self.post_disconnect(user)

  ##
  # @brief Conduct pre-disconnect process
  # @param user Request user
  async def pre_disconnect(self, user):
    # Send system message
    message = gettext_lazy('Leave {name} from {room}').format(name=str(user), room=self.room.name)
    await self.channel_layer.group_send(
      self.group_name, {
        'type': 'send_group_message',
        'msg_type': 'system',
        'ids': ['message'],
        'message': message,
      }
    )

  ##
  # @brief Conduct post-disconnect process
  # @param user Request user
  async def post_disconnect(self, user):
    # Delete user data from player list
    target = g_quizstates.get_state(self.group_name)

    if target is not None:
      target.update_player(self.get_client_key(user), do_delete=True)

      if not target.has_player():
        g_quizstates.del_state(self.group_name)

  ##
  # @brief Send group message
  # @param event Event data
  async def send_group_message(self, event):
    try:
      content = {
        'type': event['msg_type'],
        'datetime': self.now(),
      }
      content.update(dict([(key, event[key]) for key in event['ids']]))
      # Send message
      await self.send_json(content=content)
    except Exception as ex:
      self.logger.error(f'[{self.group_name}]Send group message: {ex}')

  # ===============================
  # = Define each command process =
  # ===============================
  ##
  # @brief Reset current quiz status
  # @param user Request user
  # @param target Instance of QuizState
  # @param data Dummy data (Not used)
  async def reset_quiz(self, user, target, data):
    is_owner = await self.is_owner(user)

    if is_owner:
      await database_sync_to_async(self.room.reset)()
      score = await self.get_score()
      # Update score and register relevant instance
      target.update_score(score)
      # Send message
      message = gettext_lazy('Status reset is completed')
      await self.channel_layer.group_send(
        self.group_name, {
          'type': 'send_group_message',
          'msg_type': 'resetCompleted',
          'ids': ['message'],
          'message': str(message),
        }
      )

  ##
  # @brief Reset current quiz status
  # @param user Request user
  # @param target Instance of QuizState
  # @param data Dummy data (Not used)
  async def get_next_quiz(self, user, target, data):
    is_owner = await self.is_owner(user)

    if is_owner:
      max_question = await self.get_max_question()
      quiz, index = await target.get_quiz(max_question)
      # Send
      message = gettext_lazy('The next quiz is received.')
      await self.channel_layer.group_send(
        self.group_name, {
          'type': 'send_group_message',
          'msg_type': 'sentNextQuiz',
          'ids': ['data', 'index', 'message'],
          'data': quiz,
          'index': index,
          'message': str(message),
        }
      )

  ##
  # @brief Received quiz
  # @param user Request user
  # @param target Instance of QuizState
  # @param data Dummy data (Not used)
  async def received_quiz(self, user, target, data):
    is_completed = target.update_member_status(self.get_client_key(user))

    if is_completed:
      message = gettext_lazy('All players received the quiz.')
      await self.channel_layer.group_send(
        self.group_name, {
          'type': 'send_group_message',
          'msg_type': 'sentAllQuizzes',
          'ids': ['message'],
          'message': str(message),
        }
      )

  ##
  # @brief Change state from the members cannot answer quiz to the members can do that.
  # @param user Request user
  # @param target Instance of QuizState
  # @param data Dummy data (Not used)
  async def start_answer(self, user, target, data):
    is_owner = await self.is_owner(user)

    if is_owner:
      await target.answering_phase()
      await self.channel_layer.group_send(
        self.group_name, {
          'type': 'send_group_message',
          'msg_type': 'startedAnswering',
          'ids': [],
        }
      )

  ##
  # @brief Collect player's answer and store memory
  # @param user Request user
  # @param target Instance of QuizState
  # @param data User's answer
  async def answer_quiz(self, user, target, data):
    can_answer = await target.can_answer()

    if can_answer:
      target.update_answer(self.get_client_key(user), data)

  ##
  # @brief Change state from the members can answer quiz to the members cannot do that.
  # @param user Request user
  # @param target Instance of QuizState
  # @param data Dummy data (Not used)
  async def stop_answer(self, user, target, data):
    is_owner = await self.is_owner(user)

    if is_owner:
      await target.received_all_answers_phase()
      message = gettext_lazy('Responses have ended. No more responses will be accepted.')
      await self.channel_layer.group_send(
        self.group_name, {
          'type': 'send_group_message',
          'msg_type': 'stoppedAnswering',
          'ids': ['message'],
          'message': str(message),
        }
      )

  ##
  # @brief Collect all player's answer and send them to owner
  # @param user Request user
  # @param target Instance of QuizState
  # @param data Dummy data (Not used)
  async def get_answers(self, user, target, data):
    is_owner = await self.is_owner(user)

    if is_owner:
      answers, correct_answer = await target.get_answers()
      message = gettext_lazy('All player’s answers are received.')
      await self.channel_layer.group_send(
        self.group_name, {
          'type': 'send_group_message',
          'msg_type': 'sentAnswers',
          'ids': ['data', 'correctAnswer', 'message'],
          'data': answers,
          'correctAnswer': correct_answer,
          'message': str(message),
        }
      )

  ##
  # @brief Update player's score
  # @param user Request user
  # @param target Instance of QuizState
  # @param data Judgement result for each player
  async def send_result(self, user, target, data):
    is_owner = await self.is_owner(user)

    if is_owner:
      max_question = await self.get_max_question()
      results, is_ended = await target.update_state(max_question, data)
      # Create response message
      if is_ended:
        message = gettext_lazy('All quizzes have been asked. Please press the reset button.')
      else:
        message = gettext_lazy('The score is updated. Please next quiz.')

      await self.channel_layer.group_send(
        self.group_name, {
          'type': 'send_group_message',
          'msg_type': 'shareResult',
          'ids': ['data', 'isEnded', 'message'],
          'data': results,
          'isEnded': is_ended,
          'message': str(message),
        }
      )

  ##
  # @brief Receive message from WebSocket
  # @param content Event data
  async def receive_json(self, content):
    try:
      command = content['command']
      data = content.get('data', None)
      target = g_quizstates.get_state(self.group_name)
      func_table = {
        'resetQuiz': self.reset_quiz,
        'getNextQuiz': self.get_next_quiz,
        'receivedQuiz': self.received_quiz,
        'startAnswer': self.start_answer,
        'answerQuiz': self.answer_quiz,
        'stopAnswer': self.stop_answer,
        'getAnswers': self.get_answers,
        'sendResult': self.send_result,
      }
      # execute command
      await func_table[command](self.scope['user'], target, data)
    except Exception as ex:
      self.logger.error(f'[{self.group_name}] {ex}')