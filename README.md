# Quiz App
## Assumption
I assume that host environment is satisfied with the following conditions.

| Name | Detail | Command |
| :---- | :---- | :---- |
| Device | Raspberry Pi 4 Model B Rev 1.1 | `cat /proc/cpuinfo \| sed -e "s/\s\s*/ /g" \| grep -oPi "(?<=model)(.*)" \| tr -d ':'` |
| Architecture | aarch64 (64bit) | `uname -m` |
| OS | Ubuntu 22.04.4 LTS | `cat /etc/os-release \| grep -oP '(?<=PRETTY_NAME=")(.*)(?=")'` |

## Preparation
### Common
1. Install `git`, `docker`, and `docker-compose` to your machine and enable each service because I execute python application (`Django`), https-portal (`Ruby` and `nginx`), `redis`, and `PostgreSQL` via Docker containers.

1. Run the following command and change current directory to the project.

    ```bash
    git clone https://github.com/tnakagami/quiz-app.git
    ```

1. Create `.env` files by following markdown files.

    | Target | Path | Detail |
    | :---- | :---- | :---- |
    | django | `./container_envs/django/.env` | [README.md](./container_envs/django/README.md) |
    | postgres | `./container_envs/postgres/.env` | [README.md](./container_envs/postgres/README.md) |

1. After that, create also `.env` file in the top directory of current project. The `.env` file consists of the following environment variables.

    | Envrionment variable name | Example | Enables (option) |
    | :---- | :---- | :---- |
    | `APP_DOMAINS` | `localhost -> http://django:8001` | See [https-portal](https://github.com/SteveLTN/https-portal) for details. |
    | `APP_ACCESS_PORT` | 8443 | from 1025 to 65535 |
    | `APP_ARCHITECTURE` | arm64v8 | amd64, arm32v5, arm32v6, arm32v7, arm64v8, i386, mips64le, ppc64le, riscv64, s390x |
    | `APP_TIMEZONE` | Asia/Tokyo | UTC, Asia/Tokyo, etc. |
    | `APP_VPN_ACCESS_IP` | 10.100.0.3 | 10.100.0.3, 10.17.31.123, etc. |
    | `APP_WIREGUARD_IP` | 10.100.0.2 | 10.100.0.2, 10.17.31.2, etc. |
    | `APP_WIREGUARD_PORT` | 51820 | 51012, 51013, etc. |

    Please see [env.sample](./env.sample) for details.

### Create local-network
Execute the following command and press "Enter" key. It's used to access to web server (`Django`) via VPN access.

```bash
./wrapper.sh create-network
```

### Setup wireguard environment variables
1. Create the `wireguard/envs/.env` file.

    | Envrionment variable name | Overview | Example |
    | :---- | :---- | :---- |
    | `SERVERURL` | Public domain name on your server | `SERVERURL=example.com` |
    | `PEERS` | Peer names which are separated by comma | `PEERS=PublicServer,OtherServer` |
    | `PEERDNS` | Peer DNS server. In general, you don't have to change this field. | `PEERDNS=8.8.8.8,10.0.11.1` |
    | `INTERNAL_SUBNET` | Internal subnet address. In general you don't have to change this field.  | `INTERNAL_SUBNET=10.0.11.0/24` |
    | `MTU` | Maximum Transmission Unit. In general you don't have to change this field. | `MTU=1380` |
    | `KEEP_ALIVE` | Keep alive. In general you don't have to change this field. | `KEEP_ALIVE=25` |
    | `ALLOWEDIPS` | Allowd ips to access this network. In general you don't have to change this field. | `ALLOWEDIPS=10.0.11.0/24` |

    Please see [env.sample](./wireguard/envs/env.sample) for details.

1. Create `01-routing-localnet.conf` file to [conf.up.d](wireguard/configs/iptables_script/conf.up.d) and [conf.down.d](wireguard/configs/iptables_script/conf.down.d).
Please see [README.md](./wireguard/configs/iptables_script/README.md) for details.

## Build
Run the following command to create docker images.

```bash
./wrapper.sh build
# or docker-compose build --build-arg UID="$(id -u)" --build-arg GID="$(id -g)"
```

## Create all containers
### In the case of production
To get real certification via `https-portal`, you need to modify `docker-compose.yml` file.

```yml
  https-portal:
    image: steveltn/https-portal:1.25
    container_name: https-portal.quiz-app
    restart: always
    environment:
      - STAGE=production # Change environment variable from `local` to `production`
      - NUMBITS=4096
    # other settings
```

### All containers creation
Execute the following command to start relevant services.

```bash
./wrapper start
```

### In the case of development
To access web page using `https:` request, you need to copy relevant certificate which is registered in `https-portal` to client machine. The detail is shown below.

1. Copy target certificate from `https-portal`.

    ```bash
    # In the host environment
    ./wrapper start
    # Several minutes later... Specifically, the https-portal’s output log includes "s6-rc: info: service legacy-services successfully started".
    docker cp https-portal.quiz-app:/var/lib/https-portal/default_server/default_server.crt .
    ```

1. Download the certificate to client machine.
1. Install the certificate as "Trusted Root Certification Authorities".

## Initialize Database
Run the following command to create relevant tables in your database.

```bash
./wrapper.sh migrate
```

## Copy peer config file of WireGuard to host machine
If you want to access to `admin site` in Django, you should use VPN access provided from WireGuard application.
Therefore, after creating all containers, you need to conduct the following activities.

1. Move to `wireguard/configs/peer_XXXX` directory and check whether config file is created or not.

    For example, if you define `PublicServer` as `PEERS` in `wireguard/envs/.env`, you can find `peer_PublicServer` direcotry.

1. After that, download `peer_XXXX.conf` to your host machine.
1. Finally, set your global ip to `AllowedIPs` and access to your website via VPN access.

    For instance, the modified `AllowedIPs` is `AllowedIPs = 10.0.11.0/24, 1.12.123.234/30`.

## Access to web site
Enter your domain to address-bar of web browser and move to the target page.
Specifically, access to `http://your-domain-name:${APP_ACCESS_PORT}/` via web browser.

For example, you can access to web page by using `http://1.12.123.234:8443`.