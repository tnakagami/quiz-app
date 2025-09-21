from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy
from utils.models import (
  bool_converter,
  get_current_time,
  BaseModel,
)
from . import validators
import urllib.parse

UserModel = get_user_model()

class GenreQuerySet(models.QuerySet):
  ##
  # @brief Collect active genres
  # @return Queryset whose `is_enabled` column is `True`
  def collect_active_genres(self):
    return self.filter(is_enabled=True)

  ##
  # @brief Collect active genres
  # @return Queryset that `is_enabled` column is `True` and the number of `quizzes` is greater than 0
  def collect_valid_genres(self):
    return self.annotate(quiz_counts=models.Count('quizzes', filter=models.Q(quizzes__is_completed=True))) \
               .filter(quiz_counts__gt=0, is_enabled=True)

class Genre(BaseModel):
  class Meta:
    ordering = ('name', '-created_at')

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

  ##
  # @brief Check whether request user has a update permission
  # @param user Request user
  # @return bool Judgement result
  # @retval True  The request user can update instance
  # @retval False The request user cannot update instance
  def has_update_permission(self, user):
    return user.has_manager_role()

  ##
  # @brief Check whether request user has a delete permission
  # @param user Request user
  # @return False It's always False
  def has_delete_permission(self, user):
    return False

  ##
  # @brief Check the length of each record in csv file
  # @param row Target row of csv file
  # @return bool Judgement result
  # @retval True  File format is valid
  # @retval False File format is invalid
  @staticmethod
  def length_checker(row):
    ##
    # CSV header format
    # Creator Genre name
    return len(row) == 1

  ##
  # @brief Check csv file format
  # @param rows All rows of csv file
  # @return bool Judgement result
  # @retval True  File format is valid
  # @retval False File format is invalid
  @staticmethod
  def record_checker(rows):
    genre_set = {data[0] for data in rows}
    # Get genre set based on database records
    genre_names = Genre.objects.filter(name__in=list(genre_set)).values_list('name', flat=True)
    target_genre = {name for name in genre_names}
    # Calculate common elements between original set and generated one based on database
    common_genre = genre_set & target_genre

    if common_genre:
      genres = Genre.objects.filter(name__in=list(common_genre)).order_by('name')
      genres = ','.join([str(instance) for instance in genres])
      # Create output data
      is_valid = False
      err = ValidationError(
        gettext_lazy('The csv file includes invalid genre(s). Details: %(genres)s'),
        code='invalid_file',
        params={'genres': genres},
      )
    else:
      is_valid = True
      err = None

    return is_valid, err

  ##
  # @brief Create instances from list data
  # @param cls This class object
  # @param rows All rows of csv file
  # @return instances Genres created without saving itself
  @classmethod
  def get_instances_from_list(cls, rows):
    genre_set = {data[0] for data in rows}
    instances = [cls(name=name, is_enabled=True) for name in genre_set]

    return instances

  ##
  # @brief Write active genres
  # @param cls This class object
  # @param filename Output csv filename
  # @return response Instance of django.http.HttpResponse
  @classmethod
  def get_response_kwargs(cls, filename):
    # Convert filename with encoding `UTF-8`
    name = urllib.parse.quote(filename.encode('utf-8'))
    # Create output data
    queryset = cls.objects.collect_active_genres().order_by('name')
    rows = ([obj.name] for obj in queryset.iterator())
    kwargs = {
      'rows': rows,
      'header': ['Name'],
      'filename': f'genre-{name}.csv',
    }

    return kwargs

class QuizQuerySet(models.QuerySet):
  ##
  # @brief Collect quizzes based on user
  # @param user Instance of UserModel
  # @return Queryset
  def user_relevant_quizzes(self, user):
    if user.has_manager_role():
      queryset = self.select_related('creator', 'genre').all()
    else:
      queryset = user.quizzes.all()

    return queryset

  ##
  # @brief Collect active quiz
  # @param queryset Input queryset
  # @param creators Input creators
  # @param genres Input genres
  # @parma is_and_op As using the "AND" operator, it is `True`
  # @return Queryset which consists of some creators, some genres, or both of them
  # @pre The variable type of creators and genres consists of one of `model instance`, `list`, and `QuerySet`.
  def collect_quizzes(self, queryset=None, creators=None, genres=None, is_and_op=False):
    if queryset is None:
      queryset = self.filter(is_completed=True)
    conditions = {}
    # Create condition for creators
    if creators is not None:
      if isinstance(creators, (list, models.QuerySet)):
        conditions['creator__in'] = list(creators)
      else:
        conditions['creator'] = creators
    # Create condition for genres
    if genres is not None:
      if isinstance(genres, (list, models.QuerySet)):
        conditions['genre__in'] = list(genres)
      else:
        conditions['genre'] = genres
    # In the case of existing any conditions
    if conditions:
      cond_op = models.Q.AND if is_and_op else models.Q.OR
      q_cond = models.Q()
      # Create query condition
      for key, val in conditions.items():
        q_cond.add(models.Q(**{key: val}), cond_op)
      # Filtering
      queryset = queryset.filter(q_cond).order_by('pk').distinct()
    # Ordering by genre's name
    queryset = queryset.order_by('genre__name')

    return queryset

class Quiz(BaseModel):
  class Meta:
    ordering = ('genre__name',)

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
    return self._split_text(self.question or gettext_lazy('(Not set)'))

  ##
  # @brief Get string object for the answer
  # @return text A part of a sentence
  def get_short_answer(self):
    return self._split_text(self.answer or gettext_lazy('(Not set)'))

  ##
  # @brief Check whether request user has a update permission
  # @return bool Judgement result
  # @retval True  The request user can update instance
  # @retval False The request user cannot update instance
  def has_update_permission(self, user):
    return self.creator.pk == user.pk or user.has_manager_role()

  ##
  # @brief Check the length of each record in csv file
  # @param row Target row of csv file
  # @return bool Judgement result
  # @retval True  File format is valid
  # @retval False File format is invalid
  @staticmethod
  def length_checker(row):
    ##
    # CSV header format
    # Creator ID,Genre name,Question,Answer,IsCompleted
    return len(row) == 5

  ##
  # @brief Extract specific columns
  # @param row Target row of csv file
  # @return Extracted record which includes specific columns
  @staticmethod
  def record_extractor(row):
    ##
    # Extract `Creator ID` and `Genre name`
    return (row[0], row[1])

  ##
  # @brief Check csv file format
  # @param rows All rows of csv file
  # @param user The request user
  # @exception ValidationError Invalid input
  @staticmethod
  def record_checker(rows, user):
    creator_set = {str(val) for val, _ in rows}
    genre_set = {name for _, name in rows}
    creator_email_set = {val for val in creator_set if '@' in val}
    creator_pk_set = creator_set - creator_email_set
    # Create validator
    genre_validator = validators.CustomCSVDataValidator(
      model_class=Genre,
      exception_field_name=gettext_lazy('genre'),
      base_qs=Genre.objects.collect_active_genres(),
    )
    creator_validator = validators.CustomCSVDataValidator(
      model_class=UserModel,
      exception_field_name=gettext_lazy('creator'),
      base_qs=UserModel.objects.collect_creators(),
    )
    if user.has_manager_role():
      user_email, user_pk = None, None
    else:
      user_email, user_pk = {user.email,}, {str(user.pk),}
    # Validate each target
    genre_validator.validate(genre_set, 'name__in', 'name')
    creator_validator.validate(creator_email_set, 'email__in', 'email', specific_data=user_email)
    creator_validator.validate(creator_pk_set, 'pk__in', 'pk', specific_data=user_pk, use_uuid=True)

  ##
  # @brief Create instance from list data
  # @param cls This class object
  # @param row Target row data of csv file
  # @return instance Quiz created without saving itself
  @classmethod
  def get_instance_from_list(cls, row):
    key = row[0]
    condition = {'email': key} if '@' in key else {'pk': key}
    # Create arguments
    kwargs = {
      'creator': UserModel.objects.get(**condition),
      'genre': Genre.objects.get(name=row[1]),
      'question': row[2],
      'answer': row[3],
      'is_completed': bool_converter(row[4]),
    }
    instance = cls(**kwargs)

    return instance

  ##
  # @brief Write relevant quizzes
  # @param cls This class object
  # @param filename Output csv filename
  # @param ids Quiz ids
  # @return kwargs Dictionary data
  @classmethod
  def get_response_kwargs(cls, filename, ids):
    # Convert filename with encoding `UTF-8`
    name = urllib.parse.quote(filename.encode('utf-8'))
    # Create output data
    queryset = cls.objects.select_related('creator', 'genre').filter(pk__in=list(ids)).order_by('genre__name', 'creator__screen_name')
    rows = ([str(obj.creator.pk), obj.genre.name, obj.question, obj.answer, obj.is_completed] for obj in queryset.iterator())
    kwargs = {
      'rows': rows,
      'header': ['Creator.pk', 'Genre', 'Question', 'Answer', 'IsCompleted'],
      'filename': f'quiz-{name}.csv',
    }

    return kwargs

  ##
  # @brief Get relevant quiz data
  # @param user Instance of UserModel
  # @return quizzes List of dict which includes each element of Quiz
  @classmethod
  def get_quizzes(cls, user):
    # In the case of that user is manager or superuser
    if user.has_manager_role():
      queryset = cls.objects.select_related('creator', 'genre').all()
    # In the case of that user is creator
    else:
      queryset = cls.objects.select_related('creator', 'genre').filter(creator=user)
    # Setup data
    quizzes = [
      {
        'pk': str(instance.pk),
        'creator': str(instance.creator),
        'genre': str(instance.genre),
        'question': instance.get_short_question(),
        'answer': instance.get_short_answer(),
        'is_completed': instance.is_completed,
      } for instance in queryset.order_by('pk')
    ]

    return quizzes

class QuizRoomQuerySet(models.QuerySet):
  ##
  # @brief Collect relevant quiz room
  # @return Queryset The queryset consists of room owner is user or user is included into assigned members
  # @pre The user's role is either `GUEST` or `CREATOR`
  def collect_relevant_rooms(self, user):
    if user.has_manager_role():
      queryset = self.select_related('owner').prefetch_related('genres', 'creators', 'members').all()
    else:
      owner_rooms = user.quiz_rooms.all()
      valid_assigned_rooms = user.assigned_rooms.all().exclude(is_enabled=False)
      queryset = (owner_rooms | valid_assigned_rooms).order_by('pk').distinct().order_by('name', '-created_at')

    return queryset

class QuizRoom(BaseModel):
  class Meta:
    ordering = ('name', '-created_at')

  owner = models.ForeignKey(
    UserModel,
    verbose_name=gettext_lazy('Owner'),
    on_delete=models.CASCADE,
    related_name='quiz_rooms',
  )
  name = models.CharField(
    gettext_lazy('Quiz room name'),
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
    related_name='assigned_rooms',
    blank=True,
    verbose_name=gettext_lazy('Room members'),
    help_text=gettext_lazy('Members assigned to the quiz room'),
  )
  max_question = models.PositiveIntegerField(
    gettext_lazy('Max question'),
    validators=[MinValueValidator(1)],
    help_text=gettext_lazy('The maximum number of questions'),
  )
  use_typewriter_effect = models.BooleanField(
    gettext_lazy('Use typewriter effect'),
    default=False,
    help_text=gettext_lazy('Describes whether typewriter effect is used or not.'),
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
  # @brief Check whether the request user is owner or not
  # @param user Requested user
  # @return bool Judmgement result
  # @retval True  The request user is owner
  # @retval False The request user is not owner
  def is_owner(self, user):
    return self.owner.pk == user.pk

  ##
  # @brief Check whether the request user can access to the quiz room or not
  # @param user Requested user
  # @return bool Judmgement result
  # @retval True  The request user can access
  # @retval False The request user cannot access
  def is_assigned(self, user):
    return all([
      self.is_enabled,
      user.is_player(),
      any([
        self.members.filter(pk__in=[user.pk]).exists(),
        self.is_owner(user),
      ])
    ])

  ##
  # @brief Reset score
  def reset(self):
    if self.is_enabled:
      quiz_ids = Quiz.objects.collect_quizzes(
        creators=self.creators.all(),
        genres=self.genres.all(),
      ).order_by('?').values_list('pk', flat=True)
      member_ids = self.members.all().order_by('pk').values_list('pk', flat=True)
      all_ids = list(member_ids) + [self.owner.pk]
      enable_data_counts = min(self.max_question, len(quiz_ids))
      self.score.index = 1
      self.score.status = QuizStatusType.START
      self.score.sequence = dict([(str(idx + 1), str(quiz_ids[idx])) for idx in range(enable_data_counts)])
      self.score.detail = dict([(str(pk), '0') for pk in all_ids])
      self.score.save()

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
  # @param user Request user
  # @return bool Judgement result
  # @retval True  The request user can update instance
  # @retval False The request user cannot update instance
  def has_update_permission(self, user):
    return self.owner.pk == user.pk or user.has_manager_role()

  ##
  # @brief Check whether request user has a delete permission
  # @param user Request user
  # @return bool Judgement result
  # @retval True  The request user can delete instance
  # @retval False The request user cannot delete instance
  def has_delete_permission(self, user):
    return self.has_update_permission(user) and not self.is_enabled

  ##
  # @brief Get all genre names
  # @return output Joined genre names or hyphen
  def get_genres(self):
    names = list(self.genres.all().order_by('name').values_list('name', flat=True))
    output = ','.join(names) if names else '-'

    return output

  ##
  # @brief Get all creator names
  # @return output Joined creator names or hyphen
  def get_creators(self):
    all_creators = self.creators.all().order_by('screen_name')
    names = [str(user) for user in all_creators]
    output = ','.join(names) if names else '-'

    return output

  ##
  # @brief Check genres, creators, and members
  # @exception ValidationError Some creators don't have CREATOR's role
  # @exception ValidationError Some members are not players
  def clean(self):
    creators = self.creators.all()
    members = self.members.all()
    # Check creators
    if creators and not self.is_only_creator(creators):
      raise ValidationError(
        gettext_lazy('You have to assign only creators.'),
        code='invalid_users',
      )
    # Check members
    if members and not self.is_only_player(members):
      raise ValidationError(
        gettext_lazy('You have to assign only players whose role is `Guest` or `Creator`.'),
        code='invalid_users',
      )

class QuizStatusType(models.IntegerChoices):
  # [format] name = value, label
  START            = 1, gettext_lazy('Start')
  WAITING          = 2, gettext_lazy('Waiting')
  SENT_QUESTION    = 3, gettext_lazy('Sent question')
  ANSWERING        = 4, gettext_lazy('Answering')
  RECEIVED_ANSWERS = 5, gettext_lazy('Received answers')
  JUDGING          = 6, gettext_lazy('Judging')
  END              = 7, gettext_lazy('End')

class Score(BaseModel):
  class Meta:
    ordering = ('room__name', '-index')

  room = models.OneToOneField(
    QuizRoom,
    verbose_name=gettext_lazy('Room'),
    on_delete=models.CASCADE,
    related_name='score',
  )
  status = models.IntegerField(
    gettext_lazy('Status'),
    choices=QuizStatusType.choices,
    default=QuizStatusType.START,
  )
  index = models.PositiveIntegerField(
    gettext_lazy('Index'),
    validators=[MinValueValidator(1)],
    default=1,
    help_text=gettext_lazy('The n-th question'),
  )
  sequence = models.JSONField(
    gettext_lazy('Sequence'),
    blank=True,
    default=dict,
    help_text=gettext_lazy('Sequence of questions'),
  )
  detail = models.JSONField(
    gettext_lazy('Detail score'),
    blank=True,
    default=dict,
    help_text=gettext_lazy('Detail score of each member.'),
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
    return QuizStatusType(self.status).label