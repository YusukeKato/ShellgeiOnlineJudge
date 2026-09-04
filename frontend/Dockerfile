# --- Build Stage ---
FROM node:22 AS builder

WORKDIR /app

COPY frontend/package.json frontend/yarn.lock* ./
RUN yarn install --frozen-lockfile

COPY frontend/ ./

# Viteのbuild成果物へ埋め込む公開情報だけを受け取る。
# DB資格情報などを含むルートの.envはbuild contextへコピーしない。
ARG VITE_SOJ_URL
ARG VITE_UPDATE_DATE
ARG VITE_VERSION
ARG VITE_X_URL
ARG VITE_GITHUB_REPO_URL
ARG VITE_GITHUB_AUTHOR_URL
ARG VITE_BLOG_URL
ARG VITE_MIXI2_URL
ENV VITE_SOJ_URL=${VITE_SOJ_URL} \
    VITE_UPDATE_DATE=${VITE_UPDATE_DATE} \
    VITE_VERSION=${VITE_VERSION} \
    VITE_X_URL=${VITE_X_URL} \
    VITE_GITHUB_REPO_URL=${VITE_GITHUB_REPO_URL} \
    VITE_GITHUB_AUTHOR_URL=${VITE_GITHUB_AUTHOR_URL} \
    VITE_BLOG_URL=${VITE_BLOG_URL} \
    VITE_MIXI2_URL=${VITE_MIXI2_URL}
RUN yarn typecheck
RUN yarn build

# --- Serve Stage ---
FROM nginx:alpine

# ビルド成果物をNginxの公開ディレクトリにコピー
COPY --from=builder /app/dist /usr/share/nginx/html

# 問題データを公開ディレクトリにコピー
COPY problems/ /usr/share/nginx/html/

# Nginx設定ファイルをコピー
COPY frontend/nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 443
CMD ["nginx", "-g", "daemon off;"]
