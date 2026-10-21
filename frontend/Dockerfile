# --- Build Stage ---
FROM node:22.23.4@sha256:2bd396628eceb5c999a6e43731fab69d5fb98b94ba9d9d90b5f64575c5178765 AS builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/yarn.lock* ./
RUN yarn install --frozen-lockfile

COPY frontend/ ./
COPY backend/soj_shared/version.json /app/backend/soj_shared/version.json

# Viteのbuild成果物へ埋め込む公開情報だけを受け取る。
# DB資格情報などを含むルートの.envはbuild contextへコピーしない。
ARG VITE_SOJ_URL
ARG VITE_UPDATE_DATE
ARG VITE_X_URL
ARG VITE_GITHUB_REPO_URL
ARG VITE_GITHUB_AUTHOR_URL
ARG VITE_BLOG_URL
ARG VITE_MIXI2_URL
ENV VITE_SOJ_URL=${VITE_SOJ_URL} \
    VITE_UPDATE_DATE=${VITE_UPDATE_DATE} \
    VITE_X_URL=${VITE_X_URL} \
    VITE_GITHUB_REPO_URL=${VITE_GITHUB_REPO_URL} \
    VITE_GITHUB_AUTHOR_URL=${VITE_GITHUB_AUTHOR_URL} \
    VITE_BLOG_URL=${VITE_BLOG_URL} \
    VITE_MIXI2_URL=${VITE_MIXI2_URL}
RUN yarn typecheck
RUN yarn build

# --- Serve Stage ---
FROM nginx:1.31.7-alpine@sha256:892bb2152464f0c5d8972593a5f5afaf8054552580b699d95f8ff4af08c2d33d
LABEL org.opencontainers.image.version="3.0.3"

# nginx・X11/XPM等のvendor修正版を維持し、CAの不信頼化も適用する。
RUN apk add --no-cache --upgrade ca-certificates=20261020-r0 ca-certificates-bundle=20261020-r0 libuuid=2.42.3-r1 libexpat=2.9.0-r0 pcre2=10.49-r0 zlib=1.3.2-r1 tiff=4.7.2-r0 libx11=1.8.14-r0 libxpm=3.5.20-r0

# ビルド成果物をNginxの公開ディレクトリにコピー
COPY --from=builder /app/frontend/dist /usr/share/nginx/html

# 問題データを公開ディレクトリにコピー
COPY problems/ /usr/share/nginx/html/

# Nginx設定ファイルをコピー
COPY frontend/nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 443
CMD ["nginx", "-g", "daemon off;"]
