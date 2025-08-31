# Deploy

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
root /var/www/html/;
# root /usr/share/nginx/html/;

add_header Access-Control-Allow-Origin "http://localhost" always;
# add_header Access-Control-Allow-Origin "https://shellgei-online-judge.com" always;
```

## Deploy

```sh
cd /path/to/deploy/
./deploy.bash
```

```sh
cd /path/to/ShellgeiOnlineJudge/
docker compose up --build
```

## Test
execute the following command:

```sh
# server
python3 test.py server
# local
python3 test.py local
```