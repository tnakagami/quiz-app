from django.urls import path
from . import consumers

websocket_urlpatterns = [
  path('ws/quizroom/<int:pk>', consumers.QuizConsumer.as_asgi()),
]