# SHELLGEI ONLINE JUDGE
Shell one-liner playground: https://shellgei-online-judge.com/

- [client](client/README.md): html + js + css ( + nginx)
- [server](server/README.md): php + python ( + docker)
- [data](data/README.md): problem text files
- scripts: deploy & test

## Table of Contents
- [Reference](#reference)
- [Setup](#setup)
- [Deploy](#deploy)
- [Test](#test)
- [Maintenance](#maintenance)
- [Appendix](#appendix)
- [License](#license)

## Reference
- [上田ブログ/シェル芸のトップページ](https://b.ueda.tech/?page=01434)
- [theoremoon/ShellgeiBot-Image](https://github.com/theoremoon/ShellgeiBot-Image)
- [ryuichiueda/ShellGeiData](https://github.com/ryuichiueda/ShellGeiData)
- [jiro4989/websh](https://github.com/jiro4989/websh)
- [シェル芸bot](https://x.com/minyoruminyon)

## Setup
- Ubuntu 24.04 LTS
- Ubuntu 22.04 LTS
- Amazon Linux 2023

### Install nginx
execute the following command:
```sh
# install nginx
sudo apt update && sudo apt -y upgrade
sudo apt -y install nginx

# install php
# sudo apt -y install php

# install php-fpm
sudo apt -y install php-fpm
```

### Config nginx
execute the following command:
```sh
# edit config
sudo vim /etc/nginx/conf.d/default.conf
# or
sudo vim /etc/nginx/sites-available/default
```

Update as follows:
```sh
# php8.1-fpm
location ~ \.php$ {
  fastcgi_pass unix:/run/php/php8.1-fpm.sock;
  fastcgi_param SCRIPT_FILENAME $realpath_root$fastcgi_script_name;
  # WSL2(Ubuntu 24.04 LTS): fastcgi_param SCRIPT_FILENAME <root_path>$fastcgi_script_name;
  # ex: fastcgi_param SCRIPT_FILENAME /var/www/html/$fastcgi_script_name;
  include fastcgi_params;
}
```

### Install Docker
execute the following command:
```sh
# install docker
sudo apt update && sudo apt -y upgrade
sudo apt install ca-certificates curl gnupg lsb-release
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# setup
sudo gpasswd -a $USER docker
sudo systemctl restart docker

# download image file
docker pull theoldmoon0602/shellgeibot
```

### Execution user
Change the execution user from nginx to www-data in WSL.
```sh
sudo vim /etc/php/8.3/fpm/pool.d/www.conf
sudo vim /etc/nginx/nginx.conf
```

### Permissions to execute Docker
execute the following command:
```sh
sudo visudo
```

Add the following line to the end.
```sh
# the username that executes PHP: www-data
# which docker: /usr/bin/docker
www-data ALL=(ALL) NOPASSWD: /usr/bin/docker
```

### Start Nginx
execute the following command:
```sh
sudo systemctl restart nginx
# sudo systemctl status nginx
# sudo systemctl start nginx
# sudo systemctl stop nginx
```

## Deploy
- `usr`: `/usr/share/nginx/html/`
- `var`: `/var/www/html`

execute the following command:
```sh
cd scripts
# `usr`
./deploy.bash usr server
# `var`
./deploy.bash var server

# local
./deploy.bash usr local
# or
./deploy.bash var local
```

## Test
execute the following command:
```sh
cd scripts
# server
python3 test.py server
# local test
python3 test.py local
```

## Maintenance
### Output log
```sh
cat <root_path>/shellgei_log.txt | tail -n 20
```

### Update image file
```sh
docker pull theoldmoon0602/shellgeibot
```

### Update Ubuntu
```sh
sudo apt update
sudo apt upgrade
```

### Update Amazon Linux
```sh
sudo dnf update
sudo dnf upgrade
```

### Update Let's Encrypt
```sh
sudo certbot certonly --standalone
sudo systemctl reload nginx
```

## Appendix
### How to use SSH
```sh
# sudo chmod 400 example.pem
ssh -i "example.pem" username@example.com
```

## License
- [License file](./LICENSE)
- data: Creative Commons BY-NC-ND 4.0
- client, server, scripts: Apache License 2.0