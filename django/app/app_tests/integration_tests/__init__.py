def get_current_path(response):
  return response.context['request'].path

__all__ = ['get_current_path']