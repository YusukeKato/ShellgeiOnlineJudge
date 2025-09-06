# Deploy

## Stop nginx on the host

```sh
sudo systemctl stop nginx
```

## Edit local/server

edit `frontend/src/tsx/App.tsx`

```sh
const soj_url: string = "http://localhost";
# const soj_url: string = "https://shellgei-online-judge.com";
```

edit `backend/main.py`

```sh
server_url = "http://localhost"
# server_url = "https://shellgei-online-judge.com"
```

edit `backend/conf.d/fastapi.conf`

```sh
server_name localhost;
# server_name shellgei-online-judge.com;

add_header Access-Control-Allow-Origin "http://localhost" always;
# add_header Access-Control-Allow-Origin "https://shellgei-online-judge.com" always;
```

## dot_env

edit `dot_env`

```sh
SOJ_PATH=/home/username/ShellgeiOnlineJudge/
```

execute the following command:

```sh
cp dot_env .env
```

## Deploy

```sh
cd /path/to/frontend/
yarn build
```

```sh
cd /path/to/deploy/
./deploy.bash
```

```sh
cd /path/to/ShellgeiOnlineJudge/
docker compose up -d
docker compose up --build
docker compose up --build -d
```

## Stop
```sh
docker compose down
docker system prune
docker rm $(docker ps -a -q)
```

## Test
execute the following command:

```sh
# server
python3 test.py server
# local
python3 test.py local
```