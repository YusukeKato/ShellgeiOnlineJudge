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

## .env

`.env.example` を参考に `ShellgeiOnlineJudge/.env` を作成する

## Deploy

```sh
cd /path/to/ShellgeiOnlineJudge/
docker compose up -d --build
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
