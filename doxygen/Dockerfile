ARG ARCHITECTURE=arm64v8

# =============
# Build doxygen
# =============
FROM ${ARCHITECTURE}/alpine:3.21 AS builder
ARG DOXYGEN_VERSION=1.13.2

LABEL maintainer="tnakagami"
LABEL description="Build the environment of Doxygen"

RUN    apk update \
    && apk upgrade \
    && apk add make cmake python3-dev python3 git g++ flex bison \
    && cd /tmp \
    && git clone https://github.com/doxygen/doxygen.git \
    && cd doxygen \
    && git switch -d Release_${DOXYGEN_VERSION//./_} \
    \
    # Install doxygen
    \
    && mkdir build \
    && cd build \
    && cmake -G "Unix Makefiles" .. \
    && make \
    && make install

# =============
# Release image
# =============
FROM ${ARCHITECTURE}/alpine:3.21
ARG TIMEZONE=Asia/Tokyo
ARG PUID
ARG PGID
ENV XDG_CACHE_HOME=/doxygen/cache

COPY --from=builder /tmp/doxygen/build/bin/doxygen /usr/local/bin/
COPY ./execute.sh /execute.sh

RUN     apk --update --no-cache add graphviz tzdata bash \
     && ln -sf /usr/share/zoneinfo/${TIMEZONE} /etc/localtime \
     && addgroup -g ${PGID} doxygen \
     && adduser -h /doxygen -H -S -u ${PUID} -G doxygen doxygen \
     && mkdir -p /doxygen/src \
     && mkdir -p /doxygen/cache \
     && chown doxygen:doxygen -R /doxygen/src /doxygen/cache \
     && chmod +x /execute.sh

WORKDIR /doxygen
USER doxygen

CMD ["/execute.sh"]