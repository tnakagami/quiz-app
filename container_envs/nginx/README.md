# Environment file for Nginx
Create `.env` file by following the table.

| Name | Detail | Example |
| :---- |  :---- |  :---- |
| `BASE_DOMAIN_NAME` | Fully Qualified Domain Name | example.com |
| `SSL_CERT_PATH` | Default SSL certfication file path | `/etc/nginx/default_certs/default.crt` |
| `SSL_CERTKEY_PATH` | Default SSL private key file path | `/etc/nginx/default_certs/default.key` |
| `SSL_STAPLING_VERIFY` | OCSP Stapling mode | off |
| `SSL_TRUSTED_CERTIFICATE_PATH` | Default SSL certfication file path |  `/etc/nginx/default_certs/default.crt` |

Please see [env.sample](./env.sample) for details.