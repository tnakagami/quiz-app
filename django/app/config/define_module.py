import os

def setup_default_setting():
  base_path = 'config.settings'
  app_env = os.getenv('DJANGO_EXECUTABLE_TYPE', 'development')
  setting_filename = f'{base_path}.production' if app_env == 'production' else f'{base_path}.development'
  os.environ.setdefault('DJANGO_SETTINGS_MODULE', setting_filename)