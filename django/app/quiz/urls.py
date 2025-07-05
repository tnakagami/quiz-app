from django.urls import path
from . import views

app_name = 'quiz'

urlpatterns = [
  # Genre
  path('genre-list', views.GenreListPage.as_view(), name='genre_list'),
  path('create-genre', views.CreateGenrePage.as_view(), name='create_genre'),
  path('update-genre/<pk>', views.UpdateGenrePage.as_view(), name='update_genre'),
  # Quiz
  path('quiz-list', views.QuizListPage.as_view(), name='quiz_list'),
  path('create-quiz', views.CreateQuizPage.as_view(), name='create_quiz'),
  path('update-quiz/<pk>', views.UpdateQuizPage.as_view(), name='update_quiz'),
  path('delete-quiz/<pk>', views.DeleteQuiz.as_view(), name='delete_quiz'),
  # Quiz room
  path('room-list', views.QuizRoomListPage.as_view(), name='room_list'),
  path('create-room', views.CreateQuizRoomPage.as_view(), name='create_room'),
  path('update-room/<pk>', views.UpdateQuizRoomPage.as_view(), name='update_room'),
  path('delete-room/<pk>', views.DeleteQuizRoom.as_view(), name='delete_room'),
  path('playing-room/<pk>', views.EnterQuizRoom.as_view(), name='enter_room'),
]