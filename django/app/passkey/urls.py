from django.urls import path
from . import views

app_name = 'passkey'

urlpatterns = [
  path('passkey-list', views.PasskeyListPage.as_view(), name='passkey_list'),
  path('update-passkey/<pk>', views.UpdatePasskeyPage.as_view(), name='update_passkey'),
  path('delete-passkey/<pk>', views.DeletePasskey.as_view(), name='delete_passkey'),
  # Ajax
  path('ajax/register-passkey', views.RegisterPasskey.as_view(), name='register_passkey'),
  path('ajax/complete-passkey-registration', views.CompletePasskeyRegistration.as_view(), name='complete_passkey_registration'),
  path('ajax/begin-passkey-auth', views.BeginPasskeyAuthentication.as_view(), name='begin_passkey_auth'),
]