from django.contrib.auth.backends import ModelBackend
from django.utils.translation import gettext_lazy
from passkey.models import UserPasskey

class PasskeyModelBackend(ModelBackend):
  ##
  # @brief Authentication based on username and password or passkey
  # @param request Instance of HttpRequest
  # @param username Target user's name (Default: '')
  # @param password Target user's password (Default: '')
  # @param kwargs Named arguments
  # @return user Instance of User model
  def authenticate(self, request, username='', password='', **kwargs):
    if request is None:
      raise Exception(gettext_lazy('`request` is required for passkey.backend.PasskeyModelBackend'))

    if username and password:
      request.session['passkey'] = {'passkey': False}
      user = super().authenticate(request, username=username, password=password, **kwargs)
    else:
      passkeys = request.POST.get('passkeys')
      # Check post data
      if passkeys is None:
        raise Exception(gettext_lazy('`passkeys` are required in request.POST'))
      elif passkeys != '':
        user = UserPasskey.auth_complete(request)
      else:
        user = None

    return user