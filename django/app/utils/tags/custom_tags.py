from django import template

register = template.Library()

##
# @brief URL replacer
# @param request Request instance of Django
# @param field field name
# @param value input value
# @return Encoded URL
@register.simple_tag
def url_replace(request, field, value):
  url_dict = request.GET.copy()
  url_dict[field] = str(value)

  return url_dict.urlencode()

##
# @brief Check whether request user has a update permission
# @param instance Target model instance
# @param user Request user
# @return bool Judgement result
# @retval True  The request user can update instance
# @retval False The request user cannot update instance
@register.filter
def can_update(instance, user):
  return instance.has_update_permission(user)

##
# @brief Check whether request user has a delete permission
# @param instance Target model instance
# @param user Request user
# @return bool Judgement result
# @retval True  The request user can delete instance
# @retval False The request user cannot delete instance
@register.filter
def can_delete(instance, user):
  return instance.has_delete_permission(user)