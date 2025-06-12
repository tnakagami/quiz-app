import factory
from django.utils import timezone
from faker import Factory as FakerFactory
from account import models as account_models

faker = FakerFactory.create()

def clip(target_name, max_length):
  if len(target_name) > max_length:
    clipped = target_name[:max_length]
  else:
    clipped = target_name

  return clipped

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
    else:
      friends = list(self.owner.my_friends.all())
      counts = len(friends)
      half_counts = counts // 2
      targets = friends[:half_counts] if counts > 1 else friends
      self.members.add(*targets)
      self.save()