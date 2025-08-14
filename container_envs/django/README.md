# Environment file for Django application
Create `.env` file by following the table.

| Name | Detail | Example |
| :---- |  :---- |  :---- |
| `DJANGO_EXECUTABLE_TYPE` | Definition of executive type (development or production) | development |
| `DJANGO_FIDO_SERVER_ID` | Definition of relying party ID <br /> In general, you need to set your full domain | www.example.com |
| `DJANGO_ALLOWED_HOSTS` | Virtual host list which is separated by comma | www.example.com,localhost |
| `DJANGO_SECRET_KEY` | Secret key using Django | django-secret-key |
| `DJANGO_TRUSTED_ORIGINS` | Trusted origin links which is separated by comma | `https://www.example.com,http://localhost,https://localhost:8443` |
| `DJANGO_LANGUAGE_CODE` | Language code of Django | en |
| `DJANGO_HASH_SALT` | Salt of hash value | send-salt |
| `DJANGO_EMAIL_ADDRESS` | E-mail address to send email from Django server via Google SMTP | `hogehoge@gmail.com` |
| `DJANGO_APPLICATION_PASSWORD` | Password which is used to send email via Google SMTP | `app-password-with-16-digit` |

Please see [env.sample](./env.sample) for details.