# Quiz App
## Assumption
I assume that host environment is satisfied with the following conditions.

| Name | Detail | Command |
| :---- | :---- | :---- |
| Device | Raspberry Pi 4 Model B Rev 1.1 | `cat /proc/cpuinfo \| sed -e "s/\s\s*/ /g" \| grep -oP "(?<=Model : )(.*)"` |
| Architecture | aarch64 (64bit) | `uname -m` |
| OS | Ubuntu 22.04.4 LTS | `cat /etc/os-release \| grep -oP '(?<=PRETTY_NAME=")(.*)(?=")'` |

In addition, I also assume that we use dynamic DNS based on `MyDNS`. Therefore, we use `direct_edit` script to update SSL certification provided from `Let's encrypt`.

Please see [direct_edit](./nginx/direct_edit/) for details.

## Preparation
### Common
1. Install `git`, `docker`, and `docker-compose` to your machine and enable each service because I execute python application, nginx, redis, and PostgreSQL via Docker containers.

1. Run the following command and change current directory to the project.

    ```bash
    git clone https://github.com/tnakagami/quiz-app.git
    ```

1. Create `.env` files by following markdown files.

    | Target | Path | Detail |
    | :---- | :---- | :---- |
    | common | `./container_envs/common/.env` | [README.md](./container_envs/common/README.md) |
    | nginx | `./container_envs/nginx/.env` | [README.md](./container_envs/nginx/README.md) |
    | django | `./container_envs/django/.env` | [README.md](./container_envs/django/README.md) |
    | postgres | `./container_envs/postgres/.env` | [README.md](./container_envs/postgres/README.md) |

    After that, create also `.env` file in the top directory of current project. The `.env` file consists of five environment variables.

    | Envrionment variable name | Example | Enables (option) |
    | :---- | :---- | :---- |
    | `APP_ACCESS_PORT` | 8443 | from 1025 to 65535 |
    | `APP_ARCHITECTURE` | arm64v8 | amd64, arm32v5, arm32v6, arm32v7, arm64v8, i386, mips64le, ppc64le, riscv64, s390x |
    | `APP_TIMEZONE` | Asia/Tokyo | UTC, Asia/Tokyo, etc. |
    | `APP_VPN_IP` | IP address on which the VPN client listens to Nginx | 10.0.100.3 |
    | `APP_VPN_PORT` | Port number on which the VPN client listens on Nginx | 8082 |

    Please see [env.sample](./env.sample) for details.

### Nginx
Before you build docker image, you should make `nginx/cli.ini` and `nginx/direct_edit/txtedit.conf`. By referring as sample files, you can make these files. The example is shown below.

#### `nginx/cli.ini`
The example file is in [sample.cli.ini](./nginx/sample.cli.ini).

```ini
# ==========================
# certbot configuration file
# ==========================
# Interactive mode
non-interactive = true

# Use ECC for the private key
key-type = ecdsa
elliptic-curve = secp384r1

# Plugin type
authenticator = manual
preferred-challenges = dns
manual-auth-hook = /data/direct_edit/txtregist.php
manual-cleanup-hook = /data/direct_edit/txtdelete.php

# Set E-mail
email = *** enter your-email-address ***

# Automatically agree to the terms of service of the ACME server
agree-tos = true
# Set ACME Directory Resource URI
server = https://acme-v02.api.letsencrypt.org/directory
```

#### `nginx/direct_edit/txtedit.conf`
The example file is in [sample.txtedit.conf](./nginx/direct_edit/sample.txtedit.conf).

```php
<?php
// ------------------------------------------------------------
//
// txtedit.conf
//
// ------------------------------------------------------------
?>
<?php
    $MYDNSJP_URL       = 'https://www.mydns.jp/directedit.html';
    $MYDNSJP_MASTERID  = 'hogehoge-id';     /* Enter your MyDNS ID */
    $MYDNSJP_MASTERPWD = 'foobar-password'; /* Enter your MyDNS Password */
    $MYDNSJP_DOMAIN    = getenv('BASE_DOMAIN_NAME');
?>
```

### Docker network
Run the following command to create shared network in Docker.

```bash
echo -e "y\n" | ./wrapper.sh create-network
```

## Build
Run the following command to create docker images.

```bash
./wrapper.sh build
# or docker-compose build --build-arg UID="$(id -u)" --build-arg GID="$(id -g)"
```
