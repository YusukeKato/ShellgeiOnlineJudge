# SHELLGEI ONLINE JUDGE: frontend
This repository is the webapp frontend for SHELLGEI ONLINE JUDGE.

## Setup

- reference
  - nodejs and npm: https://qiita.com/nouernet/items/d6ad4d5f4f08857644de
  - yarn and react: https://qiita.com/NaoyaOgura/items/cb94fefb6a63b7965f15
  - nginx + react: https://www.yoheim.net/blog.php?q=20180407

### Install nodejs and npm

```sh
sudo apt update && sudo upgrade -y
sudo apt install -y nodejs npm
sudo npm install n -g
sudo n stable
sudo apt purge -y nodejs npm
sudo apt autoremove -y
sudo npm install --global yarn
yarn global add create-react-app
```

## dev commands

```sh
yarn format
yarn lint
yarn build
yarn test
```