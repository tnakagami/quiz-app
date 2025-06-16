ARG ARCHITECTURE=arm64v8

From ${ARCHITECTURE}/nginx:1.27-alpine3.21-perl
ARG TIMEZONE=Asia/Tokyo

LABEL maintainer="tnakagami"
LABEL description="Build the environment of Nginx"

# Install relevant libraries
RUN    apk update \
    && apk upgrade \
    && apk add --no-cache bash tzdata gettext \
    && ln -s /usr/share/zoneinfo/${TIMEZONE} /etc/localtime \
    && echo ${TIMEZONE} > /etc/timezone \
    && echo -n > /etc/nginx/conf.d/default.conf \
    && mkdir -p /data \
    && cp -f /var/spool/cron/crontabs/root /data/original.root \
    && rm -rf /var/cache/apk/*

# Copy nginx.conf file, dns-01 script, cli.ini, and default certs file
COPY ./nginx.conf /etc/nginx/nginx.conf

CMD ["nginx"]