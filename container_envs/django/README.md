# Environment file for Django application
Create `.env` file by following the table.

| Name | Detail | Example |
| :---- |  :---- |  :---- |
| `DJANGO_SECRET_KEY` | Secret key using Django | django-secret-key |
| `DJANGO_TRUSTED_ORIGINS` | Trusted origin links which is separated by comma | `https://example.com,https://localhost:8001` |
| `DJANGO_LANGUAGE_CODE` | language code of Django | en |
| `DJANGO_SUPERUSER_EMAIL` | Email address of superuser | superuser@example.com |
| `DJANGO_SUPERUSER_PASSWORD` | Password of superuser | superuser-password |

Please see [env.sample](./env.sample) for details.