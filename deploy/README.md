# Deploy

## Switch local/server

Edit `frontend/src/tsx/App.tsx`

```ts
# const soj_url: string = "http://localhost";
# const soj_url: string = "https://shellgei-online-judge.com";
const soj_url: string = "";
```

Edit `frontend/src/functions/post_shellgei.tsx`

```ts
// const api_endpoint = soj_url + ":8000/api/shellgei";
const api_endpoint = soj_url + "/api/shellgei";
```

Edit `backend/main.py`

```py
# server_url = "http://localhost"
server_url = "https://shellgei-online-judge.com"
```

Edit `deploy/deploy.bash`

```sh
root_path="/usr/share/nginx/html/"
# root_path="/var/www/html/"
```

## Deploy

2026/02/01: docker composeだけで起動できる（ホスト側でnginxの設定と起動は必要）

```sh
cd /path/to/ShellgeiOnlineJudge/
docker compose up -d --build
```

### frontend
```sh
# cd /path/to/frontend/
# yarn install
# yarn build
```

### setup data

2026/02/01: コンテナ内で起動するため不要

```sh
# cd /path/to/deploy/
# ./deploy.bash
```

### backend

2026/02/01: コンテナ内で起動するため不要

[backend/README.md](../backend/README.md)に記載のvenv環境でuvicornかgunicornをインストールする。

```sh
cd /path/to/backend/
uvicorn main:app --host 0.0.0.0 --port 8000
# or
gunicorn --bind 0.0.0.0:8000 --workers 2 --worker-class uvicorn.workers.UvicornWorker main:app

# background
nohup uvicorn main:app --host 0.0.0.0 --port 8000 &
# or
nohup gunicorn --bind 0.0.0.0:8000 --workers 2 --worker-class uvicorn.workers.UvicornWorker main:app &

# stop
pkill uvicorn
pkill gunicorn
```

### nginx
```sh
sudo systemctl start nginx
sudo systemctl restart nginx
sudo systemctl status nginx
sudo systemctl stop nginx
```

## Test
```sh
# server
python3 test.py server
# local
python3 test.py local
```
