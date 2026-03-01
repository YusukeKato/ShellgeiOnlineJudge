# Deploy

## Setup

- install
  - docker
  - docker compose
- image
  - `docker pull theoldmoon0602/shellgeibot`

## .env

`ShellgeiOnlineJudge/.env.example` を参考に `ShellgeiOnlineJudge/.env` を作成する

## Deploy

```sh
cd /path/to/ShellgeiOnlineJudge/
docker compose up -d --build
```

## Test
```sh
cd /path/to/deploy/
python3 test.py
```

## Update Let's Encrypt
```sh
# HTTPポートを使用
sudo certbot certonly --standalone
```