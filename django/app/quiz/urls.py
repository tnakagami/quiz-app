from django.urls import path
from . import views

app_name = 'quiz'

urlpatterns = [
  path('genre-list', views.GenreListPage.as_view(), name='genre_list'),
  path('create-genre', views.CreateGenrePage.as_view(), name='create_genre'),
  path('update-genre/<pk>', views.UpdateGenrePage.as_view(), name='update_genre'),
]