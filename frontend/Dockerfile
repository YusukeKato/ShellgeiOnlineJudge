# --- Build Stage ---
FROM node:22@sha256:dd5847a04b0deee391fa145f1f4c6d214196668b6bcc7988ebed67249f226844 AS builder

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

# nginxの公開修正を含むbaseへ更新し、既存libraryの修正版も維持する。
# X11/XPMの応答・画像解析の指摘に対し、収録libraryをvendor修正版へ固定更新する。
RUN apk add --no-cache --upgrade libuuid=2.42.3-r1 libexpat=2.9.0-r0 pcre2=10.49-r0 zlib=1.3.2-r1 tiff=4.7.2-r0 libx11=1.8.14-r0 libxpm=3.5.20-r0

# ビルド成果物をNginxの公開ディレクトリにコピー
COPY --from=builder /app/frontend/dist /usr/share/nginx/html

# 問題データを公開ディレクトリにコピー
COPY problems/ /usr/share/nginx/html/

# Nginx設定ファイルをコピー
COPY frontend/nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 443
CMD ["nginx", "-g", "daemon off;"]
