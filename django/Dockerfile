ARG ARCHITECTURE=arm64v8

From ${ARCHITECTURE}/python:3.12.10-alpine3.21
ARG UID
ARG GID
ARG USERNAME=user
ARG GROUPNAME=user
ARG TIMEZONE=UTC
ENV APP_ROOT_PATH=/opt/app \
    CRYPTOGRAPHY_DONT_BUILD_RUST=1

LABEL maintainer="tnakagami"
LABEL description="Build the environment of Django application"

COPY ./pyproject.toml /opt/pyproject.toml
COPY ./tester.sh /opt/tester.sh

RUN    apk update \
    && apk upgrade \
    && apk add --no-cache bash tzdata libmagic libpq-dev pcre-dev libxml2-dev gettext \
    \
    # Install temporary libraries
    \
    && apk add --no-cache --virtual .build-deps \
               gcc musl-dev libffi-dev g++ libgcc libstdc++ libxslt-dev \
               python3-dev libc-dev linux-headers openssl-dev cargo curl shadow \
    && ln -s /usr/share/zoneinfo/${TIMEZONE} /etc/localtime \
    && echo ${TIMEZONE} > /etc/timezone \
    && pip install --upgrade pip setuptools \
    && pip install poetry \
    \
    # Create user
    \
    && groupadd -g ${GID} ${GROUPNAME} \
    && useradd \
         --no-log-init \
         --shell /bin/bash \
         --create-home --home-dir /opt/home \
         --gid ${GID} --uid ${UID} \
         ${USERNAME} \
    && mkdir -p ${APP_ROOT_PATH} \
    && chown -R ${USERNAME}:${GROUPNAME} /opt/home /opt/tester.sh \
    && chmod 755 /opt/tester.sh \
    \
    # Install relevant libraries
    \
    && cd /opt \
    \
    # Install mandatory libraries
    \
    && poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi \
    && cd / \
    \
    # Delete temporary libraries
    \
    && apk del .build-deps \
    && chown -R ${USERNAME}:${GROUPNAME} /opt/poetry.lock \
    && rm -rf /root/.cache /var/cache/apk/* /tmp/*

WORKDIR ${APP_ROOT_PATH}
USER ${USERNAME}

EXPOSE 8001

CMD ["daphne", "-b", "0.0.0.0", "-p", "8001", "--ping-interval", "10", "--ping-timeout", "120", "--proxy-headers", "config.asgi:application"]