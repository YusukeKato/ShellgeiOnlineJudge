# Maintenance

## Update docker image file

```sh
docker pull theoldmoon0602/shellgeibot
```

## Update Ubuntu

```sh
sudo apt update
sudo apt upgrade
```

## Update Amazon Linux

```sh
sudo dnf update
sudo dnf upgrade
```

## Update Let's Encrypt

```sh
sudo certbot certonly --standalone
sudo systemctl reload nginx
```

## How to use SSH

```sh
# sudo chmod 400 example.pem
ssh -i "example.pem" username@example.com
```