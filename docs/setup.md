# Setup

## Environment
- Ubuntu 24.04 LTS (+WSL2)
- Ubuntu 22.04 LTS
- Amazon Linux 2023

## Setup nginx

### Install
execute the following command:

```sh
sudo apt update && sudo apt -y upgrade
# Amazon Linux 2023: sudo dnf update && sudo dnf upgrade
sudo apt -y install nginx
sudo apt -y install php-fpm
```

### Config
execute the following command:

```sh
sudo vim /etc/nginx/nginx.conf
# or
sudo vim /etc/nginx/conf.d/default.conf
# or
sudo vim /etc/nginx/sites-available/default
```

Update as follows:

```sh
# ex:
root /usr/share/nginx/html/soj/main/;
root /var/www/html/soj/main/;

# example: php8.1-fpm
location ~ \.php$ {
  fastcgi_pass unix:/run/php/php8.1-fpm.sock;
  fastcgi_param SCRIPT_FILENAME $realpath_root$fastcgi_script_name;
  # or: fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
  # WSL2(Ubuntu 24.04 LTS): fastcgi_param SCRIPT_FILENAME <root_path>$fastcgi_script_name;
  # ex: fastcgi_param SCRIPT_FILENAME /var/www/html/$fastcgi_script_name;
  include fastcgi_params;
}
```

## Setup Docker

### Install
execute the following command:

```sh
sudo apt update && sudo apt -y upgrade
sudo apt install ca-certificates curl gnupg lsb-release
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

### Settings
execute the following command:

```sh
sudo gpasswd -a $USER docker
sudo systemctl restart docker
```

### Download image file
execute the following command:

```sh
docker pull theoldmoon0602/shellgeibot
```

### Execution user
Change the execution user from nginx to www-data in WSL.

```sh
sudo vim /etc/php/8.3/fpm/pool.d/www.conf
# ex:
# listen = /run/php/php8.3-fpm.sock
# listen.owner = www-data
# listen.group = www-data
# listen.mode = 0660
# user = www-data
# group = www-data
sudo vim /etc/nginx/nginx.conf
# ex:
# user  www-data;
```

### Permissions to execute Docker
execute the following command:

```sh
sudo visudo
```

Add the following line to the end.

```sh
# the username that executes PHP: www-data
# $ which docker: /usr/bin/docker
www-data ALL=(ALL) NOPASSWD: /usr/bin/docker
```

## Start nginx
execute the following command:

```sh
sudo systemctl start nginx
sudo systemctl restart nginx
sudo systemctl status nginx
sudo systemctl stop nginx
```