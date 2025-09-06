# SHELLGEI ONLINE JUDGE: backend
This repository is the webapp backend for SHELLGEI ONLINE JUDGE.

## Environment
- FastAPI
- Python
- nginx

## setup
```sh
sudo apt install python3-venv
# sudo dnf install python3
python3 -m venv ~/venv
source ~/venv/bin/activate
```

```sh
pip install --no-cache-dir -r requirements.txt
```

## check

```sh
ruff format /backend/
ruff check /backend/
mypy /backend/
```

## 参考
下記記事を参考にさせていただきました。

- FastAPI + nginx: https://qiita.com/junzai/items/4b737a4fafbe888bc709