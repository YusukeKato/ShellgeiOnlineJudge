# Setup

## Environment
- Ubuntu 24.04 LTS (+WSL2)
- Ubuntu 22.04 LTS
- Amazon Linux 2023

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