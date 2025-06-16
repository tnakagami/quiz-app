import pytest
from django.urls import reverse
from app_tests import status, factories

@pytest.mark.utils
@pytest.mark.view
def test_index_view_get_access_in_utils(client):
  url = reverse('utils:index')
  response = client.get(url)

  assert response.status_code == status.HTTP_200_OK