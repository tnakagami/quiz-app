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