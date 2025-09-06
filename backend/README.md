# SHELLGEI ONLINE JUDGE: backend
This repository is the webapp backend for SHELLGEI ONLINE JUDGE.

- FastAPI
- nginx

## venv

```sh
sudo apt install python3-venv
python3 -m venv ~/venv
source ~/venv/bin/activate
```

## install

```sh
pip install --no-cache-dir -r requirements.txt
```

## fastapi

```sh
gunicorn --bind 0.0.0.0:8000 --workers 2 --worker-class uvicorn.workers.UvicornWorker main:app
```