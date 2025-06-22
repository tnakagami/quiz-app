from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy
from .models import User, RoleApproval, IndividualGroup

class CustomUserChangeForm(UserChangeForm):
  class Meta:
    model = User
    fields =  ('email', 'screen_name', 'password', 'role', 'is_staff', 'is_superuser')

class CustomUserCreationForm(UserCreationForm):
  class Meta:
    model = User
    fields = ('email', 'screen_name', 'role',)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
  fieldsets = (
    (None, {'fields': ('email', 'screen_name', 'password', 'role')}),
    (gettext_lazy('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    (gettext_lazy('Important dates'), {'fields': ('last_login',)}),
  )
  add_fieldsets = (
    (None, {
      'classes': ('wide',),
      'fields': ('email', 'password1', 'password2', 'screen_name', 'role', 'is_active'),
    }),
  )

  form = CustomUserChangeForm
  add_form = CustomUserCreationForm
  list_display = ('email', 'screen_name', 'role', 'is_active', 'is_staff', 'is_superuser')
  list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
  search_fields = ('email', 'screen_name', 'role')
  ordering = ('email', 'screen_name')

@admin.register(RoleApproval)
class RoleApprovalAdmin(admin.ModelAdmin):
  model = RoleApproval
  fields = ('user', 'requested_date', 'is_completed')
  list_display = ('user', 'requested_date', 'is_completed')
  list_filter = ('is_completed',)
  search_fields = ('user__email', 'user__screen_name', 'is_completed')

@admin.register(IndividualGroup)
class IndividualGroupAdmin(admin.ModelAdmin):
  model = IndividualGroup
  fields = ('owner', 'name')
  list_display = ('owner', 'name')
  list_filter = ('owner', 'name')
  search_fields = ('owner__email', 'owner__screen_name', 'name')