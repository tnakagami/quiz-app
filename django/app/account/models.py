from django.db import models
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.utils.translation import gettext_lazy
from django.core.exceptions import ValidationError
from utils.models import get_current_time, convert_timezone, BaseModel

def _get_code():
  current_time = get_current_time()
  code = convert_timezone(current_time, is_string=True, strformat='Ymd-His.u')

  return code

class CustomUserManager(BaseUserManager):
  use_in_migrations = True

  ##
  # @brief Create new user with email and password
  # @param email User's email address
  # @param password User's password
  # @param extra_fields Additional fields
  # @return user Instance of User model
  # @exception ValueError The `email` is not set.
  def _create_user(self, email, password, **extra_fields):
    if not email:
      raise ValueError(gettext_lazy('The given email must be set.'))
    email = self.normalize_email(email)
    user = self.model(email=email, **extra_fields)
    user.set_password(password)
    user.save(using=self._db)

    return user

  ##
  # @brief Create normal user
  # @param email User's email address
  # @param password User's password (default is None)
  # @param extra_fields Additional fields
  # @return Instance of User model
  def create_user(self, email, password=None, **extra_fields):
    extra_fields.setdefault('is_staff', False)
    extra_fields.setdefault('is_superuser', False)

    return self._create_user(email, password, **extra_fields)

  ##
  # @brief Create super user
  # @param email User's email address
  # @param password User's password (default is None)
  # @param extra_fields Additional fields
  # @return Instance of User model
  # @exception ValueError At least one of is_staff and is_superuser is not True.
  def create_superuser(self, email, password=None, **extra_fields):
    extra_fields.setdefault('is_staff', True)
    extra_fields.setdefault('is_superuser', True)

    if extra_fields.get('is_staff') is not True:
        raise ValueError(gettext_lazy('Superuser must have is_staff=True.'))
    if extra_fields.get('is_superuser') is not True:
        raise ValueError(gettext_lazy('Superuser must have is_superuser=True.'))

    return self._create_user(email, password, **extra_fields)

class RoleType(models.IntegerChoices):
  MANAGER = 1, gettext_lazy('Manager')
  CREATOR = 2, gettext_lazy('Creator')
  GUEST   = 3, gettext_lazy('Guest')

class User(AbstractBaseUser, PermissionsMixin, BaseModel):
  email = models.EmailField(
    gettext_lazy('email address'),
    max_length=128,
    unique=True,
    help_text=gettext_lazy('Required. 128 characters allowing only Unicode characters, in addition to @, ., -, and _.'),
  )
  code = models.CharField(
    gettext_lazy('code'),
    max_length=22,
    default=_get_code,
  )
  screen_name = models.CharField(
    gettext_lazy('screen name'),
    max_length=128,
    blank=True,
    help_text=gettext_lazy('Optional. 128 characters or fewer.'),
  )
  password = models.CharField(
    gettext_lazy('password'),
    max_length=128,
    help_text=gettext_lazy('It must contain at least four types which are an alphabet (uppercase/lowercase), a number, and a symbol.'),
  )
  is_staff = models.BooleanField(
    gettext_lazy('staff status'),
    default=False,
    help_text=gettext_lazy('Designates whether the user can log into this admin site or not.'),
  )
  is_superuser = models.BooleanField(
    gettext_lazy('superuser status'),
    default=False,
    help_text=gettext_lazy('Designates whether the user is a superuser or not.'),
  )
  is_active = models.BooleanField(
    gettext_lazy('active'),
    default=False,
    help_text=gettext_lazy('Designates whether this user should be treated as active. Unselect this instead of deleting accounts.'),
  )
  role = models.IntegerField(
    gettext_lazy('Role'),
    choices=RoleType.choices,
    default=RoleType.GUEST,
  )
  friends = models.ManyToManyField(
    'self',
    related_name='my_friends',
    blank=True,
    verbose_name=gettext_lazy('My friends'),
    symmetrical=False,
  )

  objects = CustomUserManager()

  EMAIL_FIELD = 'email'
  USERNAME_FIELD = 'email'
  REQUIRED_FIELDS = []

  ##
  # @brief Get string object when the instance is called as `str(instance)`
  # @return screen name or email address
  # @note If screen name is blank then, return email address
  def __str__(self):
    return self.screen_name or self.email

  ##
  # @brief Judge whether user's role is MANAGER or not
  # @return True  If user's role is     MANAGER
  # @return False If user's role is not MANAGER
  def is_manager(self):
    return self.role == RoleType.MANAGER

  ##
  # @brief Judge whether user's role is CREATOR or not
  # @return True  If user's role is     CREATOR
  # @return False If user's role is not CREATOR
  def is_creator(self):
    return self.role == RoleType.CREATOR

  ##
  # @brief Judge whether user's role is GUEST or not
  # @return True  If user's role is     GUEST
  # @return False If user's role is not GUEST
  def is_guest(self):
    return self.role == RoleType.GUEST

class RoleApprovalQuerySet(models.QuerySet):
  ##
  # @brief Collect users which role is not approved
  # @return QuerySet that user's role is still Guest
  def collect_targets(self):
    return self.filter(is_completed=False)

class RoleApproval(BaseModel):
  class Meta:
    ordering = ('-requested_date', )

  objects = RoleApprovalQuerySet.as_manager()

  user = models.ForeignKey(
    User,
    verbose_name=gettext_lazy('Candidate for approval'),
    on_delete=models.CASCADE,
    related_name='approvals',
  )
  requested_date = models.DateTimeField(
    verbose_name=gettext_lazy('Requested time'),
    default=get_current_time,
  )
  is_completed = models.BooleanField(
    gettext_lazy('Approval status'),
    default=False,
    help_text=gettext_lazy("Designates whether this user's role has already been approved or not."),
  )

  ##
  # @brief Validate inputs
  # @exception ValidationError User's request is duplicated.
  def clean(self):
    super().clean()
    # Check the registering status
    is_invalid = RoleApproval.objects.filter(user=self.user).exists()

    if is_invalid:
      raise ValidationError(
        gettext_lazy('Your request has already registered.'),
        code='duplication_user',
      )

  ##
  # @brief Get string object when the instance is called as `str(instance)`
  # @return String object of user
  def __str__(self):
    return str(self.user)

  ##
  # @brief Save model instance to database
  # @param args positional arguments
  # @param kwargs named arguments
  def save(self, *args, **kwargs):
    self.full_clean()
    super().save(*args, **kwargs)

class IndividualGroup(BaseModel):
  class Meta:
    ordering = ('name', )

  owner = models.ForeignKey(
    User,
    verbose_name=gettext_lazy('Group owner'),
    on_delete=models.CASCADE,
    related_name='group_owners',
  )
  name = models.CharField(
    gettext_lazy('group name'),
    max_length=128,
    help_text=gettext_lazy('Required. 128 characters or fewer.'),
  )
  members = models.ManyToManyField(
    User,
    related_name='group_members',
    verbose_name=gettext_lazy('Group members'),
  )

  ##
  # @brief Get string object when the instance is called as `str(instance)`
  # @return Group name with owner's name
  def __str__(self):
    return f'{self.name}({self.owner})'

  ##
  # @brief Check whether assigned members are valid or not.
  # @exception ValidationError Invalid members are assigned.
  def clean(self):
    super().clean()

    if self._exists_invalid_members():
      raise ValidationError(
        gettext_lazy("Invalid member list. Some members are assigned except owner's friends."),
        code='invalid_members',
      )

  ##
  # @brief Check whether these members are assigned from owner's friends or not
  # @return True  Some members are assigned except owner's friends.
  # @return False All members are assigned from owner's friends.
  def _exists_invalid_members(self):
    friends = self.owner.friends.all().values_list('id', flat=True)
    is_invalid = self.members.exclude(id__in=list(friends)).exists()

    return is_invalid

  ##
  # @brief Save model instance to database
  # @param args positional arguments
  # @param kwargs named arguments
  def save(self, *args, **kwargs):
    self.full_clean()
    super().save(*args, **kwargs)