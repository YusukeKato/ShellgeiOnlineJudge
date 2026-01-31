# --- Build Stage ---
FROM node:22 AS builder

WORKDIR /app

COPY frontend/package.json frontend/yarn.lock* ./
RUN yarn install --frozen-lockfile

COPY frontend/ ./
RUN yarn build

# --- Serve Stage ---
FROM nginx:alpine

# ビルド成果物をNginxの公開ディレクトリにコピー
COPY --from=builder /app/build /usr/share/nginx/html

# 問題データを公開ディレクトリにコピー
COPY problems/ /usr/share/nginx/html/

# Nginx設定ファイルをコピー
COPY frontend/nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]