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
    && apk add --no-cache php php-mbstring php-openssl certbot \
    && echo -n > /etc/nginx/conf.d/default.conf \
    && mkdir -p /etc/letsencrypt \
    && mkdir -p /etc/nginx/templates \
    && mkdir -p /data \
    && rm -rf /var/cache/apk/*

# Setup environemnt variables
ENV BASE_DOMAIN_NAME=example.com \
    SSL_CERT_PATH=/etc/nginx/default_certs/default.crt \
    SSL_CERTKEY_PATH=/etc/nginx/default_certs/default.key \
    SSL_STAPLING_VERIFY=off \
    SSL_TRUSTED_CERTIFICATE_PATH=/etc/nginx/default_certs/default.crt \
    VPN_ACCESS_IP=10.0.100.3 \
    VPN_ACCESS_PORT=8080

# Setup volume data
VOLUME ["/etc/letsencrypt"]

# Copy nginx.conf file, dns-01 script, cli.ini, and default certs file
COPY ./nginx.conf /etc/nginx/nginx.conf
COPY ./direct_edit /data/direct_edit
COPY ./cli.ini /data/cli.ini
COPY ./local_certs /etc/nginx/default_certs
# Copy main shell script
COPY ./execute.sh /execute.sh
# Change mode and copy original cron file
RUN    chmod 755 /execute.sh \
    && chmod 600 /data/direct_edit/*.conf \
    && chmod 700 /data/direct_edit/*.php \
    && cp -f /var/spool/cron/crontabs/root /data/original.root

EXPOSE 443

CMD ["/execute.sh"]