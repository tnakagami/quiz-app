import factory
from factory.fuzzy import FuzzyChoice, FuzzyText
from django.db.models.signals import post_save
from django.utils import timezone
from faker import Factory as FakerFactory
from account import models as account_models
from quiz import models as quiz_models
from passkey import models as passkey_models

faker = FakerFactory.create()

def clip(target_name, max_length):
  if len(target_name) > max_length:
    clipped = target_name[:max_length]
  else:
    clipped = target_name

  return clipped

# Account app
class UserFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = account_models.User

  email = factory.Sequence(lambda idx: clip(f'user{idx}@example.com', 128).lower())
  screen_name = factory.LazyAttribute(lambda instance: clip(faker.name(), 128))
  password = factory.LazyAttribute(lambda instance: faker.pystr(min_chars=12, max_chars=128))

  @factory.post_generation
  def friends(self, create, extracted, **kwargs):
    if not create or not extracted:
      # Simple build, or nothing to add, do nothing.
      return None

    # Add the iterable of groups using bulk addition
    self.friends.add(*extracted)
    self.save()

class RoleApprovalFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = account_models.RoleApproval

  user = factory.SubFactory(UserFactory)
  requested_date = factory.LazyFunction(timezone.now)
  is_completed = False

class IndividualGroupFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = account_models.IndividualGroup

  owner = factory.SubFactory(UserFactory)
  name = factory.LazyAttribute(lambda instance: faker.pystr(min_chars=3, max_chars=128))

  @factory.post_generation
  def members(self, create, extracted, **kwargs):
    if not create:
      return None

    if extracted:
      self.members.add(*extracted)
      self.save()
    else:
      friends = list(self.owner.my_friends.all())
      counts = len(friends)
      half_counts = counts // 2
      targets = friends[:half_counts] if counts > 1 else friends
      self.members.add(*targets)
      self.save()

# Quiz app
class GenreFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = quiz_models.Genre

  name = factory.Sequence(lambda idx: '{}{}'.format(faker.pystr(min_chars=1, max_chars=64), idx))
  is_enabled = True

class QuizFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = quiz_models.Quiz

  creator = factory.SubFactory(UserFactory)
  genre = factory.SubFactory(GenreFactory)
  question = FuzzyText(length=1024)
  answer = FuzzyText(length=1024)
  is_completed = False

@factory.django.mute_signals(post_save)
class QuizRoomFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = quiz_models.QuizRoom

  owner = factory.SubFactory(UserFactory)
  name = factory.LazyAttribute(lambda instance: faker.pystr(min_chars=1, max_chars=128))
  max_question = factory.LazyAttribute(lambda instance: faker.pyint(min_value=1, max_value=256, step=1))
  use_typewriter_effect = False
  is_enabled = False
  score = factory.RelatedFactory('app_tests.factories.ScoreFactory', factory_related_name='room')

  @factory.post_generation
  def genres(self, create, extracted, **kwargs):
    if not create or not extracted:
      # Simple build, or nothing to add, do nothing.
      return None

    # Add the iterable of groups using bulk addition
    self.genres.add(*extracted)
    self.save()

  @factory.post_generation
  def creators(self, create, extracted, **kwargs):
    if not create or not extracted:
      # Simple build, or nothing to add, do nothing.
      return None

    # Add the iterable of groups using bulk addition
    self.creators.add(*extracted)
    self.save()

  @factory.post_generation
  def members(self, create, extracted, **kwargs):
    if not create or not extracted:
      # Simple build, or nothing to add, do nothing.
      return None

    # Add the iterable of groups using bulk addition
    self.members.add(*extracted)
    self.save()

def gen_dict(max_count):
  pairs = ((faker.pystr(min_chars=2, max_chars=5), faker.pyint(min_value=1, max_value=256, step=1)) for _ in range(max_count))
  ret = dict(pairs)

  return ret

@factory.django.mute_signals(post_save)
class ScoreFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = quiz_models.Score

  room = factory.SubFactory(QuizRoomFactory, score=None)
  index = factory.LazyAttribute(lambda instance: faker.pyint(min_value=1, max_value=256, step=1))
  sequence = factory.LazyAttribute(lambda instance: gen_dict(3))
  detail = factory.LazyAttribute(lambda instance: gen_dict(5))

class UserPasskeyFactory(factory.django.DjangoModelFactory):
  class Meta:
    model = passkey_models.UserPasskey

  class Params:
    platform_types = ['Apple', 'Amazon', 'Microsoft', 'Google', 'Unknown']

  user = factory.SubFactory(UserFactory)
  name = factory.LazyAttribute(lambda instance: faker.pystr(min_chars=1, max_chars=255))
  is_enabled = True
  platform = FuzzyChoice(Params.platform_types)
  credential_id = factory.Sequence(lambda idx: '{}{}'.format(faker.pystr(min_chars=1, max_chars=192), idx))
  token = factory.LazyAttribute(lambda instance: faker.pystr(min_chars=255, max_chars=255))