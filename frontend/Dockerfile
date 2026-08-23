# --- Build Stage ---
FROM node:22 AS builder

WORKDIR /app

COPY frontend/package.json frontend/yarn.lock* ./
RUN yarn install --frozen-lockfile

COPY frontend/ ./

# Reactのbuild成果物へ埋め込む公開情報だけを受け取る。
# DB資格情報などを含むルートの.envはbuild contextへコピーしない。
ARG REACT_APP_SOJ_URL
ARG REACT_APP_UPDATE_DATE
ARG REACT_APP_VERSION
ARG REACT_APP_X_URL
ARG REACT_APP_GITHUB_REPO_URL
ARG REACT_APP_GITHUB_AUTHOR_URL
ARG REACT_APP_BLOG_URL
ARG REACT_APP_MIXI2_URL
ENV REACT_APP_SOJ_URL=${REACT_APP_SOJ_URL} \
    REACT_APP_UPDATE_DATE=${REACT_APP_UPDATE_DATE} \
    REACT_APP_VERSION=${REACT_APP_VERSION} \
    REACT_APP_X_URL=${REACT_APP_X_URL} \
    REACT_APP_GITHUB_REPO_URL=${REACT_APP_GITHUB_REPO_URL} \
    REACT_APP_GITHUB_AUTHOR_URL=${REACT_APP_GITHUB_AUTHOR_URL} \
    REACT_APP_BLOG_URL=${REACT_APP_BLOG_URL} \
    REACT_APP_MIXI2_URL=${REACT_APP_MIXI2_URL}
RUN yarn build

# --- Serve Stage ---
FROM nginx:alpine

# ビルド成果物をNginxの公開ディレクトリにコピー
COPY --from=builder /app/build /usr/share/nginx/html

# 問題データを公開ディレクトリにコピー
COPY problems/ /usr/share/nginx/html/

# Nginx設定ファイルをコピー
COPY frontend/nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 443
CMD ["nginx", "-g", "daemon off;"]
