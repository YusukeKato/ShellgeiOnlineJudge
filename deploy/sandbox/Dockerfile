FROM golang:1.26.11-alpine3.24@sha256:ae52b5bc6ed045a9ed26ab03dc19327a802a9cc9aa8b27ed57f5c6b60579b0bb AS apt-ca
# 固定済みCAを初回APT用に使い、runtimeには追加しない。
RUN apk add --no-cache --upgrade ca-certificates=20261020-r0 ca-certificates-bundle=20261020-r0

# 公式Ubuntuの最小rootfsを使用し、ShellgeiBotImageの実行file・layerを継承しない。
FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS problem-data

COPY --from=apt-ca /etc/ssl/certs/ca-certificates.crt /tmp/soj-apt-ca.pem
COPY ci/prepare_apt.sh /tmp/soj-prepare-apt.sh

# Gitは取得revisionの記録にだけ使用し、実行用imageへ持ち込まない。
RUN sh /tmp/soj-prepare-apt.sh ubuntu /tmp/soj-apt-ca.pem \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git ca-certificates=20260816ubuntu0.24.04.2 \
    && rm -f /tmp/soj-apt-ca.pem /tmp/soj-prepare-apt.sh /etc/apt/apt.conf.d/99soj-apt-bootstrap \
    && rm -rf /var/lib/apt/lists/*

# refを固定しないGit ADDはbuildごとにdefault branchのHEADを解決する。
# RUN git cloneだけではlayer cacheが古い内容を再利用するため、この取得方法を使う。
ADD --keep-git-dir=true https://github.com/ryuichiueda/ShellGeiData.git /ShellGeiData/
RUN git -C /ShellGeiData rev-parse HEAD > /shellgeidata-revision \
    && rm -rf /ShellGeiData/.git

# textimgだけを修正版Go・固定moduleでbuildし、Go環境は実行用imageへ持ち込まない。
FROM apt-ca AS textimg-build
# 更新済みGo verifierとOS storeをapt-caから継承する。
WORKDIR /build
COPY deploy/sandbox/textimg/go.mod deploy/sandbox/textimg/go.sum ./
ENV CGO_ENABLED=0 GOTOOLCHAIN=local
RUN sha256sum go.mod go.sum > /tmp/locks.sha256 \
    && go build -mod=readonly -trimpath -o /out/textimg github.com/jiro4989/textimg/v3 \
    && sha256sum -c /tmp/locks.sha256

# 静的linkしたGo標準libraryと使用moduleのlicenseを実行fileと一緒に配布する。
RUN mkdir -p /out/licenses/go \
    && cp /usr/local/go/LICENSE /out/licenses/go/ \
    && go list -mod=readonly -deps -f '{{with .Module}}{{.Dir}}{{end}}' github.com/jiro4989/textimg/v3 \
       > /tmp/module-dirs \
    && sort -u /tmp/module-dirs | while IFS= read -r module_dir; do \
       if [ -n "$module_dir" ]; then \
         license_dir="/out/licenses/${module_dir#/go/pkg/mod/}"; \
         mkdir -p "$license_dir"; \
         find "$module_dir" -maxdepth 1 -type f \( -iname 'license*' -o -iname 'notice*' -o -iname 'copying*' \) \
           -exec cp '{}' "$license_dir/" \; ; \
       fi; \
       done

FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
LABEL org.opencontainers.image.version="3.0.3"

COPY --from=apt-ca /etc/ssl/certs/ca-certificates.crt /tmp/soj-apt-ca.pem
COPY ci/prepare_apt.sh /tmp/soj-prepare-apt.sh

# Ubuntuの署名済みrepositoryからsecurity更新を適用する。確定した生成物はIDで固定しscanする。
# 推奨packageや開発環境を導入せず、全92問・runnerの固定操作とtextimgに必要なpackageを追加する。
RUN sh /tmp/soj-prepare-apt.sh ubuntu /tmp/soj-apt-ca.pem \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y --no-install-recommends \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       bash coreutils gawk grep sed findutils bc rs tar \
       libc6=2.39-0ubuntu8.12 libc-bin=2.39-0ubuntu8.12 locales=2.39-0ubuntu8.12 \
       imagemagick-6.q16 fonts-noto-cjk libbrotli1=1.1.0-2ubuntu0.1 \
    && localedef -i ja_JP -f UTF-8 ja_JP.UTF-8 \
    && rm -f /tmp/soj-apt-ca.pem /tmp/soj-prepare-apt.sh /etc/apt/apt.conf.d/99soj-apt-bootstrap \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* \
    && find / -xdev -type f -perm /6000 -exec chmod a-s {} +

COPY --from=problem-data /ShellGeiData/ /ShellGeiData/
COPY --from=problem-data /shellgeidata-revision /usr/local/share/soj/shellgeidata-revision
COPY --from=textimg-build /out/textimg /usr/local/bin/textimg
COPY --from=textimg-build /out/licenses/ /usr/local/share/licenses/textimg/
COPY deploy/sandbox/policy.xml /etc/ImageMagick-6/policy.xml
ENV LANG=ja_JP.UTF-8 \
    SHELL=/bin/bash \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
WORKDIR /work
# 待機用。network・read-only・capability・tmpfs・資源制限はrunnerが作成時に強制する。
CMD ["/bin/sleep", "infinity"]
