from django.urls import path
from . import consumers

websocket_urlpatterns = [
  path('ws/quizroom/<pk>', consumers.QuizConsumer.as_asgi()),
]