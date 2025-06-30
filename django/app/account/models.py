from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.utils.translation import gettext_lazy
from django.core.mail import send_mail
from utils.models import (
  DualListbox,
  get_current_time,
  convert_timezone,
  BaseModel,
)

def _get_code():
  current_time = get_current_time()
  code = convert_timezone(current_time, is_string=True, strformat='Ymd-His.u')

  return code

class RoleType(models.IntegerChoices):
  # [format] name = value, label
  MANAGER = 1, gettext_lazy('Manager')
  CREATOR = 2, gettext_lazy('Creator')
  GUEST   = 3, gettext_lazy('Guest')

class CustomUserQuerySet(models.QuerySet):
  ##
  # @brief Get normal users
  # @return Queryset which is satisfied with `is_active=True`, `is_staff=False`, and `role != RoleType.MANAGER`
  def collect_valid_normal_users(self):
    return self.filter(is_active=True, is_staff=False).exclude(role=RoleType.MANAGER)

  ##
  # @brief Get creators only
  # @return Queryset which consists of creator's role
  def collect_creators(self):
    return self.filter(is_active=True, is_staff=False, role=RoleType.CREATOR)

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
    extra_fields.setdefault('role', RoleType.MANAGER)

    if extra_fields.get('is_staff') is not True:
        raise ValueError(gettext_lazy('Superuser must have is_staff=True.'))
    if extra_fields.get('is_superuser') is not True:
        raise ValueError(gettext_lazy('Superuser must have is_superuser=True.'))

    return self._create_user(email, password, **extra_fields)

  ##
  # @brief Get default queryset
  # @return Queryset based on `CustomUserQuerySet`
  def get_queryset(self):
    return CustomUserQuerySet(self.model, using=self._db)

  ##
  # @brief Get normal users
  # @return Queryset which is satisfied with `is_active=True`, `is_staff=False`, and `role != RoleType.MANAGER`
  def collect_valid_normal_users(self):
    return self.get_queryset().collect_valid_normal_users()

  ##
  # @brief Get creators only
  # @return Queryset which consists of creator's role
  def collect_creators(self):
    return self.get_queryset().collect_creators()

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
  created_at = models.DateTimeField(
    gettext_lazy('Created time'),
    default=get_current_time,
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
  # @brief Get role label
  # @return The label of RoleType
  def get_role_label(self):
    return RoleType(self.role).label

  ##
  # @brief Judge whether user's role includes MANAGER or not
  # @return bool Judgement result
  # @retval True  If user's role         includes MANAGER or user is superuser
  # @retval False If user's role doesn't include  MANAGER
  def has_manager_role(self):
    return self.role == RoleType.MANAGER or self.is_superuser

  ##
  # @brief Judge whether user's role is CREATOR or not
  # @return bool Judgement result
  # @retval True  If user's role is     CREATOR
  # @retval False If user's role is not CREATOR
  def is_creator(self):
    return self.role == RoleType.CREATOR and not self.is_superuser

  ##
  # @brief Judge whether user's role includes CREATOR or not
  # @return bool Judgement result
  # @retval True  If user's role         includes CREATOR
  # @retval False If user's role doesn't include  CREATOR
  def has_creator_role(self):
    return self.is_creator() or self.has_manager_role()

  ##
  # @brief Judge whether user's role is GUEST or not
  # @return bool Judgement result
  # @retval True  If user's role is     GUEST
  # @retval False If user's role is not GUEST
  def is_guest(self):
    return self.role == RoleType.GUEST and not self.is_superuser

  ##
  # @brief Judge whether user's role includes GUEST or not
  # @return bool Judgement result
  # @retval True  If user's role         includes GUEST
  # @retval False If user's role doesn't include  GUEST
  def has_guest_role(self):
    return self.is_guest() or self.has_creator_role()

  ##
  # @brief Judge whether user's role is GUEST or CREATOR, or not
  # @brief True  If user's role is     GUEST or CREATOR
  # @brief False If user's role is not GUEST or CREATOR
  def is_player(self):
    return self.is_guest() or self.is_creator()

  ##
  # @brief Send email to the user
  # @param subject E-mail subject
  # @param message E-mail body
  # @param from_email Sender of e-mail (default is None)
  # @param kwargs named arguments
  def email_user(self, subject, message, from_email=None, **kwargs):
    send_mail(subject, message, from_email, [self.email], **kwargs)

  ##
  # @brief Activate user
  def activation(self):
    self.is_active = True
    self.save()

  ##
  # @brief Judge whether the request of role change exists or not
  # @return bool Judgement result
  # @retval True  The request has already registered
  # @retval False There is no requests in the database
  def conducted_role_approval(self):
    return self.approvals.all().exists()

  ##
  # @brief Update role
  def update_role(self):
    self.role = RoleType.CREATOR
    self.save()

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
    help_text=gettext_lazy("Designates whether this user’s role has already been approved or not."),
  )

  ##
  # @brief Judge whether the requested user has a permission or not.
  # @param user Instance of requested user
  # @return bool Judgement result
  # @retval True  The user has a permission
  # @retval False The user does not have a permission
  @classmethod
  def has_request_permission(cls, user):
    is_guest = user.is_guest()
    is_requested = user.conducted_role_approval()

    return is_guest and not is_requested

  ##
  # @brief Change the record status and user's role
  # @param user Instance of requested user
  # @pre User's role is either GUEST or MANAGER
  def update_record(self, user):
    # In the case of that user's role is MANAGER
    if user.has_manager_role():
      # Update role of requested user
      self.user.update_role()
      self.is_completed = True
      self.save()
    # In the case of that user's role is GUEST
    else:
      self.user = user
      self.is_completed = False
      self.save()

  ##
  # @brief Get string object when the instance is called as `str(instance)`
  # @return String object of user
  def __str__(self):
    return str(self.user)

class IndividualGroup(BaseModel):
  class Meta:
    ordering = ('-created_at', 'name', )

  owner = models.ForeignKey(
    User,
    verbose_name=gettext_lazy('Group owner'),
    on_delete=models.CASCADE,
    related_name='group_owners',
  )
  name = models.CharField(
    gettext_lazy('Group name'),
    max_length=128,
    help_text=gettext_lazy('Required. 128 characters or fewer.'),
  )
  members = models.ManyToManyField(
    User,
    related_name='group_members',
    verbose_name=gettext_lazy('Group members'),
  )
  created_at = models.DateTimeField(
    gettext_lazy('Created time'),
    default=get_current_time,
  )

  ##
  # @brief Get string object when the instance is called as `str(instance)`
  # @return Group name
  def __str__(self):
    return self.name

  ##
  # @brief Check whether request user has a update permission
  # @return bool Judgement result
  # @retval True  The request user can update instance
  # @retval False The request user cannot update instance
  def has_update_permission(self, user):
    return self.owner.pk == user.pk or user.is_superuser

  ##
  # @brief Extract specific members are removed from user's friends or not
  # @param friends Input friends queryset (default is None)
  # @return rest_friends Rest friends in the group
  # @note If the number of rest friends is more than zero, the given friends are invalid.
  def extract_invalid_friends(self, friends=None):
    if friends is None:
      friends = self.owner.friends
    ids = friends.all().values_list('id', flat=True)
    rest_friends = self.members.exclude(id__in=list(ids))

    return rest_friends

  ##
  # @brief Check whether these members are assigned from owner's friends or not
  # @param members Input members queryset
  # @param friends Input friends queryset
  # @return bool Judgement result
  # @retval True  Some members are assigned except owner's friends.
  # @retval False All members are assigned from owner's friends.
  @classmethod
  def exists_invalid_members(cls, members, friends):
    ids = friends.all().values_list('id', flat=True)
    is_invalid = members.exclude(id__in=list(ids)).exists()

    return is_invalid

  ##
  # @brief Get relevant members
  # @param onwer_pk Owner's primary key
  # @param group_pk Individual group's primary key
  # @return List of dict which includes text, pk and is_selected element
  @classmethod
  def get_options(cls, owner_pk, group_pk):
    dual_listbox = DualListbox()
    callback = dual_listbox.user_cb

    try:
      owner = User.objects.get(pk=owner_pk)
      instance = cls.objects.get(pk=group_pk, owner=owner)
      queryset = instance.members.all()
    except:
      queryset = User.objects.collect_valid_normal_users()
    # Get options
    items = dual_listbox.create_options(queryset, is_selected=False, callback=callback)
    options = [dual_listbox.convertor(data) for data in items]

    return options