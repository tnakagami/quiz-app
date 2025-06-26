from django.db import models
from django.conf import settings
from django.utils import timezone, dateformat
import hashlib
import uuid
import json

class DualListbox:
  ##
  # @brief Constructor of DualListbox
  def __init__(self):
    self.user_cb = lambda instance: instance.code
    self.name_cb = lambda instance: instance.name

  ##
  # @brief Create options of dual listbox
  # @param instances Instances which consist of either list or QuerySet
  # @param is_selected Flag of whether its element is selected or not (default is True)
  # @param callback callback with its instance as argument (default is None)
  # @return output List of tuples which consist of primary-key, label-name, and selected-or-not
  def create_options(self, instances, is_selected=True, callback=None):
    if callable(callback):
      _formatter = lambda val: f'{val}({callback(val)})'
    else:
      _formatter = lambda val: f'{val}'

    return [(_formatter(instance), str(instance.pk), is_selected) for instance in instances]

  ##
  # @brief Convert tuple data to dict data
  # @param data Input tuple data
  # @return Output dictionary data
  def convertor(self, data):
    text, pk, flag = data

    return {"text": f'{text}', "value": f'{pk}', "selected": flag}

  ##
  # @brief Convert options from python object to JSON string
  # @param data Input data which consists of list of tuples
  # @return JSON data converted from input data
  def convert2json(self, data):
    return json.dumps([self.convertor(vals) for vals in data])

  ##
  # @brief Collect options of item list from the given item list
  # @param all_items All items to separate selected one or noe
  # @param selected_items Selected items (default is None)
  # @param callback Callback function (default is None)
  # @return options JSON data converted from input data
  def collect_options_of_items(self, all_items, selected_items=None, callback=None):
      if selected_items is not None:
        excluded_items = all_items.exclude(pk__in=list(selected_items.values_list('pk', flat=True)))
        selected_options = self.create_options(selected_items, is_selected=True, callback=callback)
        not_selected_options = self.create_options(excluded_items, is_selected=False, callback=callback)
        options = self.convert2json(selected_options + not_selected_options)
      else:
        options = self.convert2json(self.create_options(all_items, is_selected=False, callback=callback))

      return options

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

  ##
  # @brief Check whether request user has a update permission
  # @return bool Judgement result
  # @retval True  The request user can update instance
  # @retval False The request user cannot update instance
  def has_update_permission(self, user):
    return user.is_superuser

  ##
  # @brief Check whether request user has a delete permission
  # @return bool Judgement result
  # @retval True  The request user can delete instance
  # @retval False The request user cannot delete instance
  def has_delete_permission(self, user):
    return self.has_update_permission(user)