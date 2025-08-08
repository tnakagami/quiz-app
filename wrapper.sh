#!/bin/bash

readonly NETWORK_NAME="shared-localnet"
readonly DJANGO_CONTAINER=django.quiz-app
readonly BASE_DIR=$(cd $(dirname $0) && pwd)
readonly HTTPS_PORTAL_HTML_DIR=${BASE_DIR}/https-portal/html
readonly WIREGUARD_DIR=${BASE_DIR}/wireguard
readonly WIREGUARD_YAML_FILE=${WIREGUARD_DIR}/docker-compose.yml
readonly DOXYGEN_DIR=${BASE_DIR}/doxygen
readonly DOXYGEN_YAML_FILE=${DOXYGEN_DIR}/docker-compose.yml

function Usage() {
cat <<- _EOF
Usage: $0 command [option] ...

Enabled commands:
  create-network
    create docker network

  build
    Build docker image using Dockerfile

  start
    Start all containers

  stop
    Stop all containers

  restart
    Restart all containers

  down
    Destroy all containers

  ps
    Show the running containers

  logs
    Show logs of each container

  migrate
    Execute database migration of backend in the docker environment

  test
    Execute pytest

  cleanup [-f]
    Delete invalid containers and images

  maintenance
    change from release mode to maintenance mode

  release
    change from maintenance mode to release mode

  help | -h
    Show this message
_EOF
}

function clean_up() {
  # Delete disabled containers
  docker ps -a | grep Exited | awk '{print $1;}' | xargs -I{} docker rm -f {}
  # Delete disabled images
  docker images | grep none | awk '{print $3;}' | xargs -I{} docker rmi {}
  # Delete temporary volumes
  docker volume ls | grep -oP "\s+[0-9a-f]+$" | awk '{print $1}' | xargs -I{} docker volume rm {}
}

# ================
# = main routine =
# ================

if [ $# -eq 0 ]; then
  Usage
  exit 0
fi

while [ -n "$1" ]; do
  case "$1" in
    help | -h )
      Usage

      shift
      ;;

    create-network )
      if ! $(docker network ls | grep -q "${NETWORK_NAME}"); then
        base_ip=$(cat ${BASE_DIR}/.env | grep "APP_VPN_ACCESS_IP" | grep -oP "(?<==)((\d+|\.){5})")
        subnet="${base_ip}.0/24"
        gateway="${base_ip}.1"
        echo    "Create docker network: "
        echo    "  Name:    ${NETWORK_NAME}"
        echo    "  Subnet:  ${subnet}"
        echo    "  Gateway: ${gateway}"
        echo -n "Are you ok? (y/n [y]): "
        read is_valid

        if [ -z "${is_valid}" -o "y" == "${is_valid}" ]; then
          echo "Create docker network(bridge)"
          docker network create --driver=bridge --subnet=${subnet} --gateway=${gateway} ${NETWORK_NAME}
          docker network ls | grep ${NETWORK_NAME}
        else
          echo "Cancel to create docker network"
        fi
      else
        echo Docker network \"${NETWORK_NAME}\" already exists.
      fi

      shift
      ;;

    build )
      docker-compose build --build-arg UID="$(id -u)" --build-arg GID="$(id -g)"
      clean_up

      shift
      ;;

    start )
      {
        echo PUID=$(id -u)
        echo PGID=$(id -g)
      } > ${WIREGUARD_DIR}/envs/.ids-env
      docker-compose up -d
      docker-compose -f ${WIREGUARD_YAML_FILE} --env-file ${BASE_DIR}/.env up -d

      shift
      ;;

    stop | restart | down )
      docker-compose $1
      docker-compose -f ${WIREGUARD_YAML_FILE} $1

      shift
      ;;

    doxygen )
      shift

      case "$1" in
        build )
          docker-compose -f ${DOXYGEN_YAML_FILE} --env-file ${BASE_DIR}/.env build --build-arg PUID="$(id -u)" --build-arg PGID="$(id -g)"
          clean_up

          shift
          ;;

        start )
          docker-compose -f ${DOXYGEN_YAML_FILE} --env-file ${BASE_DIR}/.env up -d

          shift
          ;;

        stop | restart | down )
          docker-compose -f ${DOXYGEN_YAML_FILE} $1

          shift
          ;;

        * )
          shift
          ;;
      esac

      ;;

    ps )
      {
        docker-compose ps
        docker-compose -f ${WIREGUARD_YAML_FILE} ps
        docker-compose -f ${DOXYGEN_YAML_FILE} ps
      } | sed -r -e "s|\s{2,}|#|g" | awk -F'[#]' '
      BEGIN {
        maxlen_service = -1;
        maxlen_status = -1;
        maxlen_port = -1;
      }
      FNR > 1{
        _services[FNR] = $3;
        _statuses[FNR] = $4;
        _ports[FNR] = $5;
        service_len = length($3);
        status_len = length($4);
        port_len = length($5);

        if (maxlen_service < service_len) { maxlen_service = service_len; }
        if (maxlen_status < status_len) { maxlen_status = status_len; }
        if (maxlen_port < port_len) { maxlen_port = port_len; }
      }
      END {
        if (FNR > 1) {
          total_len = maxlen_service + maxlen_status + maxlen_port;
          hyphens = sprintf("%*s", total_len + 9, "");
          gsub(".", "-", hyphens);
          # Output
          printf("%-*s | %-*s | %-*s\n", maxlen_service, "Service", maxlen_status, "Status", maxlen_port, "Port");
          print hyphens;

          for (idx = 2; idx <= FNR; idx++) {
            printf("%*s | %*s | %-*s\n",
              maxlen_service, _services[idx],
              maxlen_status, _statuses[idx],
              maxlen_port, _ports[idx]);
          }
        }
      }'

      shift
      ;;

    logs )
      {
        docker-compose logs -t
        docker-compose -f ${WIREGUARD_YAML_FILE} logs -t
        docker-compose -f ${DOXYGEN_YAML_FILE} logs -t
      } | sort -t "|" -k 1,+2d

      shift
      ;;

    migrate )
      docker-compose up -d
      apps=$(find django/app -type f | grep -oP "(?<=/)([a-zA-Z]+)(?=/apps.py$)" | tr '\n' ' ')
      commands="python manage.py makemigrations ${apps}; python manage.py migrate"
      docker exec ${DJANGO_CONTAINER} bash -c "${commands}"

      shift
      ;;

    test )
      docker-compose down
      docker-compose run django /opt/tester.sh
      docker-compose down

      shift
      ;;

    cleanup )
      clean_up
      shift

      if [ "$1" = "-f" ]; then
        docker builder prune -f
        shift
      fi
      ;;

    maintenance )
      touch ${HTTPS_PORTAL_HTML_DIR}/is_maintenance
      echo maintenance mode

      shift
      ;;

    release )
      rm -f ${HTTPS_PORTAL_HTML_DIR}/is_maintenance
      echo release mode

      shift
      ;;

    * )
      shift
      ;;
  esac
done