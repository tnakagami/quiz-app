import pytest
from django.utils import timezone, dateformat
from app_tests import factories
from quiz.models import Genre

@pytest.fixture(scope='module')
def get_genres(django_db_blocker):
  with django_db_blocker.unblock():
    genres = []

    for idx in range(8):
      output = dateformat.format(timezone.now(), 'Ymd-His.u')
      name = f'quiz{idx}-{output}'

      try:
        instance = Genre.objects.get(name=name)
      except:
        instance = factories.GenreFactory(name=name, is_enabled=True)
      genres += [instance]

  return genres