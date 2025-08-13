from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy
from utils.models import (
  get_current_time,
  BaseModel,
)
import fido2.features
import json
import traceback
from base64 import urlsafe_b64encode
from fido2.server import Fido2Server
from fido2.utils import websafe_decode, websafe_encode
from fido2.webauthn import (
  PublicKeyCredentialRpEntity,
  AttestedCredentialData,
  ResidentKeyRequirement,
)
from logging import getLogger
from user_agents.parsers import parse as ua_parse

UserModel = get_user_model()

class UserPasskey(BaseModel):
  class Meta:
    ordering = ('name', '-last_used')

  user = models.ForeignKey(
    UserModel,
    verbose_name=gettext_lazy('User'),
    on_delete=models.CASCADE,
    related_name='passkeys',
  )
  name = models.CharField(
    gettext_lazy('Passkey name'),
    max_length=255,
    help_text=gettext_lazy('Required. 255 characters or fewer.'),
  )
  is_enabled = models.BooleanField(
    gettext_lazy('Passkey status'),
    default=True,
    help_text=gettext_lazy('Describes whether the passkey is enabled or not.'),
  )
  platform = models.CharField(
    gettext_lazy('Platform'),
    max_length=255,
    default='',
    help_text=gettext_lazy('Optional. 255 characters or fewer.'),
  )
  created_at = models.DateTimeField(
    gettext_lazy('Added time'),
    default=get_current_time,
  )
  last_used = models.DateTimeField(
    gettext_lazy('Last used time'),
    null=True,
    default=None,
  )
  credential_id = models.CharField(
    gettext_lazy('Credential ID'),
    max_length=255,
    unique=True,
  )
  token = models.CharField(
    gettext_lazy('Token'),
    max_length=255,
    null=False,
  )

  ##
  # @brief Get string object for the quiz room
  # @return The room name and the owner's name
  def __str__(self):
    return f'{self.user}({self.platform})'

  ##
  # @brief Check whether request user has a update permission
  # @param user Request user
  # @return bool Judgement result
  # @retval True  The request user can update instance
  # @retval False The request user cannot update instance
  def has_update_permission(self, user):
    return self.user.pk == user.pk

  ##
  # @brief Update mapping status of fido2
  def enable_json_mapping(self):
    try:
      fido2.features.webauthn_json_mapping.enabled = True
    except:
      pass

  ##
  # @brief Get credentials for requested user
  # @return credentials Decoded credentials
  def get_credentials(self):
    queryset = UserPasskey.objects.filter(user=self.user)
    credentials = [AttestedCredentialData(websafe_decode(obj.token)) for obj in queryset]

    return credentials

  ##
  # @brief Get FIDO2 server
  # @param request Instance of HttpRequest (Default: None)
  # @return server Instance of FIDO2 server
  @staticmethod
  def get_server(request=None):
    # Get server id
    if callable(settings.FIDO_SERVER_ID):
      server_id = settings.FIDO_SERVER_ID(request)
    else:
      server_id = settings.FIDO_SERVER_ID
    # Get server name
    if callable(settings.FIDO_SERVER_NAME):
      server_name = settings.FIDO_SERVER_NAME(request)
    else:
      server_name = settings.FIDO_SERVER_NAME
    # Get relying party and server
    relying_party = PublicKeyCredentialRpEntity(id=server_id, name=server_name)
    server = Fido2Server(relying_party)

    return server

  ##
  # @brief Get platform information
  # @param request Instance of HttpRequest
  # @return platform Platform name
  def get_current_platform(self, request):
    user_agent = ua_parse(request.META['HTTP_USER_AGENT'])

    if 'Safari' in user_agent.browser.family:
      platform = 'Apple'
    elif 'Chrome' in user_agent.browser.family and user_agent.os.family == 'Mac OS X':
      platform = 'Chrome on Apple'
    elif 'Android' in user_agent.os.family:
      platform = 'Google'
    elif 'Windows' in user_agent.os.family:
      platform = 'Microsoft'
    else:
      platform = 'Unknown'

    return platform

  ##
  # @brief Register a new FIDO device
  # @param request Instance of HttpRequest
  # @param data Registration data
  def register_begin(self, request):
    self.enable_json_mapping()
    server = self.get_server(request)
    auth_attachment = getattr(settings, 'KEY_ATTACHMENT', None)
    params = {
      'id': urlsafe_b64encode(self.user.pk.bytes),
      'name': getattr(self.user, UserModel.USERNAME_FIELD),
      'displayName': str(self.user),
    }
    credentials = self.get_credentials()
    # Conduct registration
    data, state = server.register_begin(
      params,
      credentials,
      authenticator_attachment=auth_attachment,
      resident_key_requirement=ResidentKeyRequirement.PREFERRED
    )
    request.session['fido2_state'] = state

    return data

  ##
  # @brief Complete the device registration
  # @param request Instance of HttpRequest
  # @return status Process status
  def register_complete(self, request):
    logger = getLogger(__name__)

    try:
      if 'fido2_state' not in request.session:
        status = {
          'code': 401,
          'message': gettext_lazy('FIDO Status can’t be found, please try again'),
        }
      else:
        self.enable_json_mapping()
        data = json.loads(request.body)
        server = self.get_server(request)
        auth_data = server.register_complete(request.session.pop('fido2_state'), response=data)
        platform = self.get_current_platform(request)
        # Update current instance data
        self.name = data.get('key_name', platform)
        self.is_enabled = True
        self.token = websafe_encode(auth_data.credential_data)
        self.platform = platform
        self.credential_id = data.get('id')
        self.save()
        status = {
          'code': 200,
          'message': 'OK',
        }
    except Exception as ex:
      logger.error(traceback.format_exc())
      logger.error(str(ex))
      status = {
        'code': 500,
        'message': gettext_lazy('Error on server, please try again later'),
      }

    return status

  ##
  # @brief Conduct authentication with passkey
  # @param request Instance of HttpRequest
  # @param data Authentication data
  @classmethod
  def auth_begin(cls, request):
    if request.user.is_authenticated:
      instance = cls(user=request.user)
      credentials = instance.get_credentials()
    else:
      credentials = []
    server = cls.get_server(request)
    data, state = server.authenticate_begin(credentials)
    request.session['fido2_state'] = state

    return data

  ##
  # @brief Complete authentication with passkey
  # @param request Instance of HttpRequest
  # @param user Instance of User model
  @classmethod
  def auth_complete(cls, request):
    logger = getLogger(__name__)
    data = json.loads(request.POST.get('passkeys'))
    credential_id = data.get('id')

    try:
      instance = cls.objects.get(credential_id=credential_id, is_enabled=True)
      instance.enable_json_mapping()
      server = instance.get_server(request)
      credentials = [AttestedCredentialData(websafe_decode(instance.token))]
      # Authentication
      cred = server.authenticate_complete(
        request.session.pop('fido2_state'),
        credentials=credentials,
        response=data,
      )
      # Update instance
      instance.last_used = get_current_time()
      is_cross_platform = instance.get_current_platform(request) == instance.platform
      request.session['passkey'] = {
        'passkey': True,
        'name': str(instance.user),
        'id': instance.pk,
        'platform': instance.platform,
        'cross_platform': is_cross_platform,
      }
      instance.save()
      user = instance.user
    except (cls.DoesNotExist, ValueError):
      user = None
    except Exception as ex:
      logger.error(str(ex))
      user = None

    return user