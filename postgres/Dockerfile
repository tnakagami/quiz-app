ARG ARCHITECTURE=arm64v8

From ${ARCHITECTURE}/postgres:17-alpine3.21
ARG TIMEZONE=Asia/Tokyo

LABEL maintainer="tnakagami"
LABEL description="Build the environment of PostgreSQL"

RUN    apk update \
    && apk upgrade \
    && apk add --no-cache bash tzdata \
    && ln -s /usr/share/zoneinfo/${TIMEZONE} /etc/localtime \
    && echo ${TIMEZONE} > /etc/timezone