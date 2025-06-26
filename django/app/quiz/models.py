from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy
from utils.models import get_current_time, BaseModel

UserModel = get_user_model()

class GenreQuerySet(models.QuerySet):
  ##
  # @brief Collect active genres
  # @return Queryset whose `is_enabled` column is `True`
  def collect_active_genres(self):
    return self.filter(is_enabled=True)

class Genre(BaseModel):
  name = models.CharField(
    gettext_lazy('Genre name'),
    max_length=128,
    unique=True,
    help_text=gettext_lazy('Required. 128 characters or fewer.'),
  )
  is_enabled = models.BooleanField(
    gettext_lazy('Enable'),
    default=True,
    help_text=gettext_lazy('Describes whether this genre is enabled or not.'),
  )
  created_at = models.DateTimeField(
    gettext_lazy('Created time'),
    default=get_current_time,
  )

  objects = GenreQuerySet.as_manager()

  ##
  # @brief Get string object for genre name
  # @return Genre name
  def __str__(self):
    return self.name

class QuizQuerySet(models.QuerySet):
  ##
  # @brief Collect active genre
  # @return Queryset which consists of some creators, some genres, or both of them
  # @pre The variable type of creators and genres consists of one of `model instance`, `list`, and `QuerySet`.
  def collect_quizzes(self, creators=None, genres=None):
    queryset = self.filter(is_completed=True)
    conditions = {}
    # Create condition for creators
    if creators is not None:
      if isinstance(creators, (list, models.QuerySet)):
        conditions['creator__pk__in'] = list(creators)
      else:
        conditions['creator__pk'] = creators.pk
    # Create condition for genres
    if genres is not None:
      if isinstance(genres, (list, models.QuerySet)):
        conditions['genre__pk__in'] = list(genres)
      else:
        conditions['genre__pk'] = genres.pk
    # In the case of existing any conditions
    if conditions:
      q_cond = models.Q()
      # Create query condition
      for key, val in conditions.items():
        q_cond.add(models.Q(**{key: val}), models.Q.OR)
      # Filtering
      queryset = queryset.filter(q_cond)

    return queryset

class Quiz(BaseModel):
  creator = models.ForeignKey(
    UserModel,
    verbose_name=gettext_lazy('Creator'),
    on_delete=models.CASCADE,
    related_name='quizzes',
  )
  genre = models.ForeignKey(
    Genre,
    verbose_name=gettext_lazy('Genre'),
    on_delete=models.CASCADE,
    related_name='quizzes',
  )
  question = models.TextField(
    gettext_lazy('Question'),
    blank=True,
    help_text=gettext_lazy('Enter the question.'),
  )
  answer = models.TextField(
    gettext_lazy('Answer'),
    blank=True,
    help_text=gettext_lazy('Enter the answer for the question.'),
  )
  is_completed = models.BooleanField(
    gettext_lazy('Creation status'),
    default=False,
    help_text=gettext_lazy('Describes whether the creation of this quiz is completed or not.'),
  )

  objects = QuizQuerySet.as_manager()

  ##
  # @brief Get string object for the question
  # @return text A part of a sentence
  def __str__(self):
    return f'{self.get_short_question()}({self.creator})'

  ##
  # @brief Split string object
  # @param sentence Input text
  # @param max_length Max length of text (default is 16)
  # @return output A part of a sentence
  def _split_text(self, sentence, max_length=16):
    length = len(sentence)

    if length > max_length:
      output = sentence[:max_length]
    else:
      output = sentence

    return output

  ##
  # @brief Get string object for the question
  # @return text A part of a sentence
  def get_short_question(self):
    return self._split_text(self.question)

  ##
  # @brief Get string object for the answer
  # @return text A part of a sentence
  def get_short_answer(self):
    return self._split_text(self.answer)

  ##
  # @brief Check whether request user has a update permission
  # @return bool Judgement result
  # @retval True  The request user can update instance
  # @retval False The request user cannot update instance
  def has_update_permission(self, user):
    return self.creator.pk == user.pk or user.has_manager_role()

class QuizRoomQuerySet(models.QuerySet):
  ##
  # @brief Collect active quiz room
  # @return Queryset whose `is_enabled` column is `True`
  def collect_active_room(self):
    return self.filter(is_enabled=True)

class QuizRoom(BaseModel):
  owner = models.ForeignKey(
    UserModel,
    verbose_name=gettext_lazy('Owner'),
    on_delete=models.CASCADE,
    related_name='quiz_rooms',
  )
  name = models.CharField(
    gettext_lazy('Quiz name'),
    max_length=128,
    help_text=gettext_lazy('Required. 128 characters or fewer.'),
  )
  genres = models.ManyToManyField(
    Genre,
    related_name='quiz_rooms',
    blank=True,
    verbose_name=gettext_lazy('Genres'),
    help_text=gettext_lazy('Genres used in the quiz room'),
  )
  creators = models.ManyToManyField(
    UserModel,
    related_name='room_creators',
    blank=True,
    verbose_name=gettext_lazy('Creators'),
    help_text=gettext_lazy('Creators used in the quiz room'),
  )
  members = models.ManyToManyField(
    UserModel,
    related_name='room_members',
    blank=True,
    verbose_name=gettext_lazy('Room members'),
    help_text=gettext_lazy('Members assigned to the quiz room'),
  )
  max_question = models.PositiveIntegerField(
    gettext_lazy('Max question'),
    validators=[MinValueValidator(1)],
    help_text=gettext_lazy('The maximum number of questions'),
  )
  is_enabled = models.BooleanField(
    gettext_lazy('Enable'),
    default=False,
    help_text=gettext_lazy('Describes whether this quiz room is enabled or not.'),
  )
  created_at = models.DateTimeField(
    gettext_lazy('Created time'),
    default=get_current_time,
  )

  objects = QuizRoomQuerySet.as_manager()

  ##
  # @brief Get string object for the quiz room
  # @return The room name and the owner's name
  def __str__(self):
    return f'{self.name}({self.owner})'

  ##
  # @brief Check whether the request user can access to the quiz room or not
  # @return bool Judmgement result
  # @retval True  The request user can access
  # @retval False The request user cannot access
  def is_assigned(self, user):
    return user.is_player() and self.members.all().filter(pk__in=[user.pk]).exists()

  ##
  # @brief Validate whether all members are creators or not
  # @param members Target members
  # @return bool Judgement result
  # @retval True  All members are creators
  # @retval False Some members's role is not `CREATOR`
  @classmethod
  def is_only_creator(cls, members):
    return all([user.is_creator() for user in members])

  ##
  # @brief Validate whether all members are players or not
  # @param members Target members
  # @return bool Judgement result
  # @retval True  All members are players
  # @retval False Some members are not players
  @classmethod
  def is_only_player(cls, members):
    return all([user.is_player() for user in members])

  ##
  # @brief Check whether request user has a update permission
  # @return bool Judgement result
  # @retval True  The request user can update instance
  # @retval False The request user cannot update instance
  def has_update_permission(self, user):
    return self.owner.pk == user.pk or user.has_manager_role()

  ##
  # @brief Check whether request user has a delete permission
  # @return bool Judgement result
  # @retval True  The request user can delete instance
  # @retval False The request user cannot delete instance
  def has_delete_permission(self, user):
    return self.has_update_permission(user) and not self.is_enabled

  ##
  # @brief Get all genre names
  # @return output Joined genre names or hyphen
  def get_genres(self):
    names = list(self.genres.all().values_list('name', flat=True))
    output = ','.join(names) if names else '-'

    return output

  ##
  # @brief Get all creator names
  # @return output Joined creator names or hyphen
  def get_creators(self):
    names = list(self.creators.all().values_list('screen_name', flat=True))
    output = ','.join(names) if names else '-'

    return output

  ##
  # @brief Check genres, creators, and members
  # @exception ValidationError Both genres and creators are not set.
  # @exception ValidationError Some creators don't have CREATOR's role
  # @exception ValidationError Some members are not players
  def clean(self):
    # Check genres and creators
    if not self.genres and not self.creators:
      raise ValidationError(
        gettext_lazy('You have to assign at least one of genres and creators to the quiz room.'),
        code='invalid_assignment',
      )
    # Check creators
    if self.creators and not self.is_only_creator(self.creators.all()):
      raise ValidationError(
        gettext_lazy('You have to assign only creators.'),
        code='invalid_users',
      )
    # Check members
    if self.members and not self.is_only_player(self.members.all()):
      raise ValidationError(
        gettext_lazy('You have to assign only players whose role is `Guest` or `Creator`.'),
        code='invalid_users',
      )

class QuizStatusType(models.IntegerChoices):
  # [format] name = value, label
  START            = 1, gettext_lazy('Start')
  WAITING          = 2, gettext_lazy('Waiting')
  SET_QUESTION     = 3, gettext_lazy('Set question')
  Answering        = 4, gettext_lazy('Answering')
  RECEIVED_ANSWERS = 5, gettext_lazy('Received answers')
  JUDGING          = 6, gettext_lazy('Judging')
  END              = 7, gettext_lazy('End')

class Score(BaseModel):
  room = models.ForeignKey(
    QuizRoom,
    verbose_name=gettext_lazy('Room'),
    on_delete=models.CASCADE,
    related_name='scores',
  )
  status = models.IntegerField(
    gettext_lazy('Status'),
    choices=QuizStatusType.choices,
    default=QuizStatusType.START,
  )
  count = models.PositiveIntegerField(
    gettext_lazy('Count'),
    validators=[MinValueValidator(1)],
    default=1,
    help_text=gettext_lazy('The n-th question'),
  )
  quiz = models.ForeignKey(
    Quiz,
    verbose_name=gettext_lazy('Quiz'),
    on_delete=models.CASCADE,
    related_name='scores',
    null=True,
  )
  scores = models.JSONField(
    gettext_lazy('Scores'),
    blank=True,
    help_text=gettext_lazy('Store the scores of each member.'),
  )

  ##
  # @brief Get string object for the quiz room
  # @return The status and the room name
  def __str__(self):
    label = self.get_status_label()

    return f'{self.room.name}({label})'

  ##
  # @brief Get status label
  # @return The label of QuizStatusType
  def get_status_label(self):
    return QuizStatusType(self.role).label