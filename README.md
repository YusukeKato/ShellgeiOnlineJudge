# SHELLGEI ONLINE JUDGE
シェル芸オンラインジャッジ

SHELLGEI ONLINE JUDGE: https://shellgei-online-judge.com/

# Shellgei Online Judge Repositories
- main: https://github.com/YusukeKato/ShellgeiOnlineJudge
- web app: https://github.com/YusukeKato/ShellgeiOnlineJudgeWeb
- server: https://github.com/YusukeKato/ShellgeiOnlineJudgeServer
- problem data: https://github.com/YusukeKato/ShellgeiOnlineJudgeData

# deploy
```sh
cd ShellgeiOnlineJudge
bash deploy_ShellgeiOnlineJudge.bash
```

# update packages
```sh
sudo dnf update
sudo dnf upgrade
```

# update ShellgeiBot-Image
```sh
docker pull theoldmoon0602/shellgeibot
```

# update HTTPS
```sh
sudo certbot certonly --standalone
sudo systemctl reload nginx
```
