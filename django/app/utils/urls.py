from django.urls import path
from . import views

app_name = 'utils'

urlpatterns = [
  path('', views.Index.as_view(), name='index'),
  path('introduction/', views.Introduction.as_view(), name='introduction'),
]