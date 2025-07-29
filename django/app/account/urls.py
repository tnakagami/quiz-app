from django.urls import path
from . import views

app_name = 'account'

urlpatterns = [
  path('', views.Index.as_view(), name='alternative'),
  path('login/', views.LoginPage.as_view(), name='login'),
  path('logout/', views.LogoutPage.as_view(), name='logout'),
  # Show/Update user profile
  path('user-profile', views.UserProfilePage.as_view(), name='user_profile'),
  path('update-profile', views.UpdateUserProfilePage.as_view(), name='update_profile'),
  # Account registration
  path('create-account', views.CreateAccountPage.as_view(), name='create_account'),
  path('create-account/done', views.DoneAccountCreationPage.as_view(), name='done_account_creation'),
  path('complete-account-creation/<token>', views.CompleteAccountCreationPage.as_view(), name='complete_account_creation'),
  # Change password
  path('change-password', views.ChangePasswordPage.as_view(), name='update_password'),
  path('change-password/done', views.DonePasswordChangePage.as_view(), name='done_password_change'),
  # Reset password
  path('reset-password', views.ResetPasswordPage.as_view(), name='reset_password'),
  path('reset-password/done', views.DonePasswordResetPage.as_view(), name='done_password_reset'),
  path('confirm-password-reset/<uidb64>/<token>', views.ConfirmPasswordResetPage.as_view(), name='confirm_password_reset'),
  path('complete-password-reset', views.CompletePasswordResetPage.as_view(), name='complete_password_reset'),
  # Change role
  path('role-change-list', views.RoleChangeRequestListPage.as_view(), name='role_change_requests'),
  path('change-role', views.CreateRoleChangeRequestPage.as_view(), name='create_role_change_request'),
  path('approve-role-change/<pk>', views.UpdateRoleApproval.as_view(), name='update_role_approval'),
  # Add friend
  path('update-friend', views.UpdateFriendPage.as_view(), name='update_friend'),
  # Check/Create/Update/Delete individual group
  path('individual-group', views.IndividualGroupListPage.as_view(), name='individual_group_list'),
  path('create-group', views.CreateIndividualGroupPage.as_view(), name='create_group'),
  path('update-group/<pk>', views.UpdateIndividualGroupPage.as_view(), name='update_group'),
  path('delete-group/<pk>', views.DeleteIndividualGroup.as_view(), name='delete_group'),
  # Ajax
  path('ajax/get-options', views.IndividualGroupAjaxResponse.as_view(), name='ajax_get_options'),
  # Download creator
  path('download/creators', views.DownloadCreatorPage.as_view(), name='download_creator'),
]