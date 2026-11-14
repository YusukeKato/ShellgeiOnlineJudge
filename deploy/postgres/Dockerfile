FROM golang:1.26.11-alpine3.24@sha256:ae52b5bc6ed045a9ed26ab03dc19327a802a9cc9aa8b27ed57f5c6b60579b0bb AS gosu-build
# Go verifierとOS storeの両方を更新し、module取得前に旧rootを除く。
RUN apk add --no-cache --upgrade ca-certificates=20261020-r0 ca-certificates-bundle=20261020-r0

# gosuの権限切替実装は維持し、修正版Goで再buildする。sourceとmodule checksumを検証する。
ADD --checksum=sha256:cd9719b775dbfedae53923c9b0dc792b66d42c51e0b36652ed6f747fbadc0164 \
    https://github.com/tianon/gosu/archive/refs/tags/1.19.tar.gz /tmp/gosu.tar.gz
WORKDIR /build
RUN tar -xzf /tmp/gosu.tar.gz \
    && cd gosu-1.19 \
    && CGO_ENABLED=0 GOTOOLCHAIN=local go build -mod=readonly -trimpath -o /out/gosu .

FROM postgres:15.20-alpine3.24@sha256:5cb339462bde5e6b617acedf6c2a3008f3aadc44a3c0507dd22226ee1279aee8
LABEL org.opencontainers.image.version="3.0.3"

# PostgreSQL・entrypoint・PGDATAは継承し、CAと必要なruntime libraryを固定versionへ更新する。
# zlibの追加memory安全性修正を含むvendor版へ限定更新し、既存のOpenSSL/libuuid固定値を維持する。
RUN apk add --no-cache --upgrade ca-certificates-bundle=20261020-r0 libcrypto3=3.5.9-r0 libssl3=3.5.9-r0 musl-utils=1.2.6-r3 libuuid=2.42.3-r1 zlib=1.4-r0 libxslt=1.1.43-r4 krb5-libs=1.22.3-r0
COPY --from=gosu-build /out/gosu /usr/local/bin/gosu
COPY --from=gosu-build /build/gosu-1.19/LICENSE /usr/local/share/licenses/gosu/LICENSE
RUN gosu nobody true
