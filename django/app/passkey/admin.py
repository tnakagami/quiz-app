from django.contrib import admin
from .models import UserPasskey

@admin.register(UserPasskey)
class UserPasskeyAdmin(admin.ModelAdmin):
  model = UserPasskey
  fields = ('name', 'is_enabled', 'platform', 'last_used', 'credential_id', 'token')
  list_display = ('name', 'is_enabled', 'platform')
  list_filter = ('name', 'is_enabled', 'platform', 'last_used')
  search_fields = ('name', 'is_enabled', 'platform', 'last_used')