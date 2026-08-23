# SHELLGEI ONLINE JUDGE: backend
This repository is the webapp backend for SHELLGEI ONLINE JUDGE.

## Environment
- FastAPI
- Python
- nginx

## setup

Poetry、rootless Docker、環境変数を含む手順は、[開発環境の構築・テスト・起動](../docs/DEVELOPMENT.md)を参照してください。

```sh
poetry install
```

## check

```sh
poetry run ruff format --check .
poetry run ruff check .
poetry run mypy .
poetry run pytest -m "not docker"
```

実際のsandboxコンテナを使用するテストは、[Docker統合テスト](./tests/integration/README.md)を参照してください。

## 参考
下記記事を参考にさせていただきました。

- FastAPI + nginx: https://qiita.com/junzai/items/4b737a4fafbe888bc709
