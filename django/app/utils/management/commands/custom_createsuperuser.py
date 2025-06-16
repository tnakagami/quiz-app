from django.contrib.auth.management.commands import createsuperuser
from django.core.management import CommandError

class Command(createsuperuser.Command):
  help = 'Create a superuser with a password non-interactively'

  def add_arguments(self, parser):
    super().add_arguments(parser)
    parser.add_argument(
      '--password', dest='password', default=None,
      help='Specifies the password for the superuser.',
    )

  def handle(self, *args, **options):
    options.setdefault('interactive', False)
    email = options.get('email')
    password = options.get('password')
    database = options.get('database')

    if not email or not password:
      raise CommandError('--email and --password are required options')

    user_data = {
      'email': email,
      'password': password,
      'screen_name': 'admin',
      'is_active': True,
    }
    exists = self.UserModel._default_manager.db_manager(database).filter(email=email).exists()

    if not exists:
      self.UserModel._default_manager.db_manager(database).create_superuser(**user_data)