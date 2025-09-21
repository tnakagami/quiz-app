#!/bin/bash

readonly NETWORK_NAME="shared-localnet"
readonly COMPOSE_CMD="docker compose"
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

  doxygen
    Execute commands with relevant to Doxygen.
    You can use `build`, `start`, `stop`, `restart`, `down` commands.

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
      ${COMPOSE_CMD} build --build-arg UID="$(id -u)" --build-arg GID="$(id -g)"
      clean_up

      shift
      ;;

    start )
      {
        echo PUID=$(id -u)
        echo PGID=$(id -g)
      } > ${WIREGUARD_DIR}/envs/.ids-env
      ${COMPOSE_CMD}                                                       up -d
      ${COMPOSE_CMD} -f ${WIREGUARD_YAML_FILE} --env-file ${BASE_DIR}/.env up -d

      shift
      ;;

    stop | restart | down )
      ${COMPOSE_CMD}                           $1
      ${COMPOSE_CMD} -f ${WIREGUARD_YAML_FILE} $1

      shift
      ;;

    doxygen )
      shift

      case "$1" in
        build )
          ${COMPOSE_CMD} -f ${DOXYGEN_YAML_FILE} --env-file ${BASE_DIR}/.env build --build-arg PUID="$(id -u)" --build-arg PGID="$(id -g)"
          clean_up

          shift
          ;;

        start )
          ${COMPOSE_CMD} -f ${DOXYGEN_YAML_FILE} --env-file ${BASE_DIR}/.env up -d

          shift
          ;;

        stop | restart | down )
          ${COMPOSE_CMD} -f ${DOXYGEN_YAML_FILE} $1

          shift
          ;;

        * )
          shift
          ;;
      esac

      ;;

    ps )
      ${COMPOSE_CMD}                           ps --format 'table {{ .Service }}\t{{ .Status }}\t{{ .Ports }}'
      ${COMPOSE_CMD} -f ${WIREGUARD_YAML_FILE} ps --format 'table {{ .Service }}\t{{ .Status }}\t{{ .Ports }}' | grep -v "SERVICE"
      ${COMPOSE_CMD} -f ${DOXYGEN_YAML_FILE}   ps --format 'table {{ .Service }}\t{{ .Status }}\t{{ .Ports }}' | grep -v "SERVICE"

      shift
      ;;

    logs )
      {
        ${COMPOSE_CMD}                           logs -t
        ${COMPOSE_CMD} -f ${WIREGUARD_YAML_FILE} logs -t
        ${COMPOSE_CMD} -f ${DOXYGEN_YAML_FILE}   logs -t
      } | sort -t "|" -k 1,+2d

      shift
      ;;

    migrate )
      ${COMPOSE_CMD} up -d
      apps=$(find django/app -type f | grep -oP "(?<=/)([a-zA-Z]+)(?=/apps.py$)" | tr '\n' ' ')
      commands="python manage.py makemigrations ${apps}; python manage.py migrate"
      docker exec ${DJANGO_CONTAINER} bash -c "${commands}"

      shift
      ;;

    test )
      ${COMPOSE_CMD} down
      ${COMPOSE_CMD} run django /opt/tester.sh
      ${COMPOSE_CMD} down
      docker ps -a | grep Exited | awk '{print $1}' | xargs docker rm -f

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