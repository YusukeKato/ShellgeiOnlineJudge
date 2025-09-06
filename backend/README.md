# SHELLGEI ONLINE JUDGE: backend
This repository is the webapp backend for SHELLGEI ONLINE JUDGE.

- FastAPI
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