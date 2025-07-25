# Setup Django
## Preparations
### Execute makemigrations and migrate
Migrations are how Django stores changes to your models and Django manages your database schema automatically by using results of migration. To do this, from the command line, run the following command.

```bash
# In the host environment
docker-compose run --rm django bash

# In the docker environment
python manage.py makemigrations utils account quiz
python manage.py migrate
```

Please remember the two-step guides to making model changes:

1. Change your models (in `models.py`).
1. Run `python manage.py makemigrations something-apps` to create migrations for those changes in your application
1. After that, execute `python manage.py migrate` command to apply those changes to the database.

### Create superuser
By referring the following table, create superuser account.

| Argument | Detail | Example |
| :---- | :---- | :---- |
| `--email` | Superuser's e-mail address | `hoge@example.com` |
| `--password` | Superuser's password | `superuser-password` |

Specifically, after definition of `email` and `password`, you can type the following command.

```bash
# In the docker environment
python manage.py custom_createsuperuser --email hoge@example.com --password superuser-password
```

### Collect static files
After that, execute the following command to get static files.

```bash
# In the docker environment
python manage.py collectstatic
```

### Create multilingual localization messages
Run the following commands to reflect translation messages.

```bash
# 
# If you need to create/update translated file, type the following commands and execute them.

# In the docker environment
django-admin makemessages -l ${DJANGO_LANGUAGE_CODE:-en}
exit # or press Ctrl + D

#
# Edit .po files using your favorite editor (e.g. vim) in the host environment.
#

# In the host environment
docker-compose run --rm django bash
# In the docker environment
django-admin compilemessages
```

## Test
### Preparation
In this project, `pytest` and pytest's third packages are used. In particular, `pytest-django` is useful when I develop web applications using the Django framework.

So, I prepare conftest.py in the top directory of `app_tests`. The details are shown below.

```python
# app_tests/conftest.py
import pytest

@pytest.fixture(scope='session', autouse=True)
def django_db_setup(django_db_setup):
  pass
```

### Execution
Run the following command to execute pytest in your pc.

```bash
# In the host environment
./wrapper.sh test
```