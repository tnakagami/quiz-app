ARG ARCHITECTURE=arm64v8

# =============
# Build doxygen
# =============
FROM ${ARCHITECTURE}/alpine:3.21 AS builder
ARG DOXYGEN_VERSION=1.13.2

LABEL maintainer="tnakagami"
LABEL description="Build the environment of Doxygen and TeX-Live"

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
    && make -j$(nproc) \
    && make install

# =============
# Build texlive
# =============
FROM ${ARCHITECTURE}/alpine:3.21 AS installer
ARG CUSTOMBIN_NAME=aarch64-alpine322.tar.xz
ENV PATH=/usr/local/bin/texlive:${PATH} \
    TL_MIRROR=https://mirror.init7.net/ctan/systems/texlive/tlnet
COPY ./texlive.profile /tmp/texlive.profile
RUN    apk update \
    && apk upgrade \
    && apk add --no-cache perl tar wget xz fontconfig \
    && cd /tmp \
    && mkdir -p /tmp/custombin \
    && wget https://ftp.math.utah.edu/pub/texlive-utah/bin/${CUSTOMBIN_NAME} \
    && tar -xvf ${CUSTOMBIN_NAME} -C /tmp/custombin --strip-components=1 \
    && mkdir -p /tmp/install-tl \
    && wget -nv https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz \
    && tar -xzf ./install-tl-unx.tar.gz -C /tmp/install-tl --strip-components=1 \
    \
    # Install texlive
    \
    && /tmp/install-tl/install-tl --custom-bin=/tmp/custombin --profile=/tmp/texlive.profile \
    && ln -sf /usr/local/texlive/*/bin/* /usr/local/bin/texlive \
    && tlmgr update --self \
    && tlmgr option repository ${TL_MIRROR} \
    && tlmgr install \
               biber \
               biblatex \
               bookmark \
               booktabs \
               fontawesome \
               hyperref \
               kpfonts \
               collection-fontsrecommended \
               collection-langjapanese \
               collection-latexextra \
               latexmk \
               listings \
               mathtools

# =============
# Release image
# =============
FROM ${ARCHITECTURE}/alpine:3.21
ARG TIMEZONE=UTC
ARG PUID
ARG PGID
ENV XDG_CACHE_HOME=/doxygen/cache \
    PATH=/usr/local/bin/texlive:${PATH}

COPY --from=builder /tmp/doxygen/build/bin/doxygen /usr/local/bin/
COPY --from=installer /usr/local/texlive /usr/local/texlive
COPY ./execute.sh /execute.sh

RUN     apk --update --no-cache add graphviz tzdata bash perl wget make \
     && ln -sf /usr/share/zoneinfo/${TIMEZONE} /etc/localtime \
     && ln -sf /usr/local/texlive/*/bin/* /usr/local/bin/texlive \
     && addgroup -g ${PGID} doxygen \
     && adduser -h /doxygen -H -S -u ${PUID} -G doxygen doxygen \
     && mkdir -p /doxygen/src \
     && mkdir -p /doxygen/cache \
     && chown doxygen:doxygen -R /doxygen/src /doxygen/cache \
     && chmod +x /execute.sh

WORKDIR /doxygen
USER doxygen

CMD ["/execute.sh"]