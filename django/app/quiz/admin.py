from django.contrib import admin
from .models import Genre, Quiz, QuizRoom, Score

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
  model = Genre
  fields = ('name', 'is_enabled')
  list_display = ('name', 'is_enabled')
  list_filter = ('name', 'is_enabled')
  search_fields = ('name', 'is_enabled')

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
  model = Quiz
  fields = ('creator', 'genre', 'is_completed')
  list_display = ('creator', 'genre', 'is_completed')
  list_filter = ('creator', 'genre', 'is_completed')
  search_fields = ('creator__email', 'creator__screen_name', 'genre__name', 'is_completed')

@admin.register(QuizRoom)
class QuizRoomAdmin(admin.ModelAdmin):
  model = QuizRoom
  fields = ('owner', 'name', 'genres', 'creators', 'is_enabled')
  list_display = ('owner', 'name', 'is_enabled')
  list_filter = ('owner', 'name', 'is_enabled')
  search_fields = ('owner__email', 'owner__screen_name', 'name', 'is_enabled')

@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
  model = Score
  fields = ('room', 'status')
  list_display = ('room', 'status')
  list_filter = ('room', 'status')
  search_fields = ('room__name', 'status')