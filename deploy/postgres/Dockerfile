FROM golang:1.26-alpine@sha256:51a7c389a5ddaf82f527191a1e9bff9928655130a44e4975dd1d7e0acf59f1ae AS gosu-build

# gosuの権限切替実装は維持し、修正版Goで再buildする。sourceとmodule checksumを検証する。
ADD --checksum=sha256:cd9719b775dbfedae53923c9b0dc792b66d42c51e0b36652ed6f747fbadc0164 \
    https://github.com/tianon/gosu/archive/refs/tags/1.19.tar.gz /tmp/gosu.tar.gz
WORKDIR /build
RUN tar -xzf /tmp/gosu.tar.gz \
    && cd gosu-1.19 \
    && CGO_ENABLED=0 GOTOOLCHAIN=local go build -mod=readonly -trimpath -o /out/gosu .

FROM postgres:15-alpine@sha256:a46e076249ce434e41203b8c1dadfaa025b9726331d72390df038385d6dc29cd
LABEL org.opencontainers.image.version="3.0.0"

# PostgreSQL・entrypoint・PGDATAは継承し、検出のあるOpenSSL・libuuidだけを固定versionへ更新する。
RUN apk add --no-cache --upgrade libcrypto3=3.5.8-r0 libssl3=3.5.8-r0 libuuid=2.42.3-r1
COPY --from=gosu-build /out/gosu /usr/local/bin/gosu
COPY --from=gosu-build /build/gosu-1.19/LICENSE /usr/local/share/licenses/gosu/LICENSE
RUN gosu nobody true
