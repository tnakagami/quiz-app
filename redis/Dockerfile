ARG ARCHITECTURE=arm64v8
FROM ${ARCHITECTURE}/redis:8-alpine
ARG TIMEZONE=UTC

LABEL maintainer="tnakagami"
LABEL description="build redis environment"

# Copy shell script
COPY ./init.sh /init.sh

# To store redis's config file
RUN    apk update \
    && apk upgrade \
    && apk add --no-cache bash tzdata \
    && ln -s /usr/share/zoneinfo/${TIMEZONE} /etc/localtime \
    && echo ${TIMEZONE} > /etc/timezone \
    && mkdir -p /usr/local/etc/redis \
    && mkdir -p /var/log/redis \
    && chmod +x /init.sh \
    && echo -n > /usr/local/etc/redis/redis.conf

EXPOSE 6379

CMD ["/init.sh"]