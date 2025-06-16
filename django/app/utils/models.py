from django.db import models
from django.conf import settings
from django.utils import timezone, dateformat
import hashlib
import uuid

##
# @brief Get current time without timezone
# @return current_time Datetime of Django
def get_current_time():
  return timezone.now()

##
# @brief Convert UTC time to specific time with timezone
# @param utc_time UTC time
# @param is_string The flag that whether output time is converted to string or not (default is False)
# @param strformat The format of output time (default is 'Y-m-d')
# @note `strformat` is used only if `is_string` is True
def convert_timezone(utc_time, is_string=False, strformat='Y-m-d'):
  output = timezone.localtime(utc_time)

  if is_string:
    output = dateformat.format(output, strformat)

  return output

##
# @brief Make hash value based on current date
# @return digest hash value of hex string with salt given by developer
def get_digest():
  current_time = get_current_time()
  message = convert_timezone(current_time, is_string=True, strformat='Y-m-d(w)')
  digest = hashlib.sha256(f'{message}#{settings.HASH_SALT}'.encode()).hexdigest()

  return digest

class BaseModel(models.Model):
  class Meta:
    abstract = True

  id = models.UUIDField(
    primary_key=True,
    default=uuid.uuid4,
    editable=False,
  )