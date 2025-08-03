import pytest
from utils.tags import room_tags
from app_tests import factories
from account.models import RoleType

@pytest.fixture(scope='module')
def get_participants_and_quizzes(django_db_blocker):
  with django_db_blocker.unblock():
    genre = factories.GenreFactory(is_enabled=True)
    creators = factories.UserFactory.create_batch(2, is_active=True, role=RoleType.CREATOR)
    members = factories.UserFactory.create_batch(3, is_active=True)
    # Create quiz
    for creator in creators:
      _ = factories.QuizFactory(creator=creator, genre=genre, is_completed=True)

  return creators, members

@pytest.mark.customtag
@pytest.mark.django_db
@pytest.mark.parametrize([
  'role',
  'has_owner_permission',
  'expected',
], [
  (RoleType.GUEST, True, True),
  (RoleType.GUEST, False, False),
  (RoleType.CREATOR, True, True),
  (RoleType.CREATOR, False, False),
], ids=[
  'guest-and-owner',
  'guest-not-owner',
  'creator-and-owner',
  'creator-not-owner',
])
def test_is_owner(get_participants_and_quizzes, role, has_owner_permission, expected):
  owner = factories.UserFactory(is_active=True, role=role)
  user = owner if has_owner_permission else factories.UserFactory(is_active=True)
  creators, members = get_participants_and_quizzes
  room = factories.QuizRoomFactory(
    owner=owner,
    creators=creators,
    members=members,
    is_enabled=True,
  )
  is_valid = room_tags.is_owner(room, user)

  assert is_valid == expected

@pytest.mark.customtag
@pytest.mark.django_db
@pytest.mark.parametrize([
  'is_updated',
  'exact_vals',
], [
  (True, ['5', '3', '2', '1']),  # three members + owner
  (False, ['0', '0', '0', '0']), # three members + owner
], ids=[
  'detail-is-updated',
  'call-reset-method-only',
])
def test_get_user_score(get_participants_and_quizzes, is_updated, exact_vals):
  creators, members = get_participants_and_quizzes
  owner = factories.UserFactory(is_active=True)
  room = factories.QuizRoomFactory(
    owner=owner,
    creators=creators,
    members=members,
    is_enabled=True,
  )
  room.reset()
  score = room.score
  _keys = score.detail.keys()

  if is_updated:
    detail = score.detail
    updated_detail = {pk: val for pk, val in zip(_keys, exact_vals)}
    score.detail = updated_detail
    score.save()
  # Call target method
  output = [room_tags.get_user_score(score, pk) for pk in _keys]

  assert len(output) == len(exact_vals)
  assert all([estimated == expected for estimated, expected in zip(output, exact_vals)])