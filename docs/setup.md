# Setup

## Environment
- Ubuntu 24.04 LTS (+WSL2)
- Ubuntu 22.04 LTS
- Amazon Linux 2023

## Docker

### Install docker

- docker, docker composeを使用できる状態にする
- 下記のインストール方法が古いかも？

```sh
sudo apt update && sudo apt -y upgrade
sudo apt install ca-certificates curl gnupg lsb-release
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

```sh
sudo curl -L https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose --version
```

### Setup docker

2026/01/31: おそらくこの設定は必要ない

```sh
# sudo gpasswd -a $USER docker
# sudo systemctl restart docker
```

```sh
# sudo visudo
```

```sh
# the username that executes PHP: www-data
# $ which docker: /usr/bin/docker
# www-data ALL=(ALL) NOPASSWD: /usr/bin/docker
```

### Download image file

```sh
docker pull theoldmoon0602/shellgeibot
```

## nginx

### Install nginx

2026/02/01: nginxをコンテナ内で動かせるようになったので不要

```sh
sudo apt update && sudo apt -y upgrade
# Amazon Linux 2023: sudo dnf update && sudo dnf upgrade
sudo apt -y install nginx
```

### Setup nginx

2026/02/01: /frontend/nginx/にconfファイルを用意

`sudo vim /etc/nginx/nginx.conf`

```sh
server {
    listen 80;
    listen 443 ssh:

    # server_name localhost;
    server_name shellgei-online-judge.com;

    # root /var/www/html/soj/;
    root /usr/share/nginx/html/soj/;

    # /apiか/api/か最後にスラッシュがあるかないかで挙動が異なるので注意
    location /api {
        # add_header Access-Control-Allow-Origin '*' always;
        # add_header Access-Control-Allow-Origin "http://localhost" always;
        add_header Access-Control-Allow-Origin "https://shellgei-online-judge.com" always;
        proxy_pass http://localhost:8080; # バックエンドは8080
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    location / {
        index  index.html;
    }
}
```