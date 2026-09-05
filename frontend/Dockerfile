# --- Build Stage ---
FROM node:22@sha256:0557ac14e0d45d02ed563067b82856ca5e7aa3437fa28d98d4350ea9c3d9494a AS builder

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
FROM nginx:alpine@sha256:72ba65eb42c10344912a84ff42408db7d34f2feb642204570ab8fc5ffd29f1d3
LABEL org.opencontainers.image.version="3.0.0"

# baseを維持し、util-linux由来の検出に対応するlibraryだけを固定更新する。
RUN apk add --no-cache --upgrade libuuid=2.42.3-r0

# ビルド成果物をNginxの公開ディレクトリにコピー
COPY --from=builder /app/frontend/dist /usr/share/nginx/html

# 問題データを公開ディレクトリにコピー
COPY problems/ /usr/share/nginx/html/

# Nginx設定ファイルをコピー
COPY frontend/nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 443
CMD ["nginx", "-g", "daemon off;"]
