# SHELLGEI ONLINE JUDGE: backend

`backend` directoryには、FastAPIによる公開Web API、内部runner API、
問題の判定、実行ログの保存、sandboxコンテナの管理を行うPythonコードがあります。

## 主な構成

- `main.py`: API endpointとapplication起動・終了処理
- `runner_main.py`: 認証付き内部runnerとsandbox poolの起動・終了処理
- `api/`: API endpoint
- `models/`: APIの入出力と実行ログのmodel
- `scripts/`: runner通信、Docker実行、判定、入力検証、DB接続とログ保持処理
- `tests/`: 単体・API・Docker統合テスト

## 開発とテスト

環境構築、Pythonの静的検査、単体テストは、
[開発環境の構築・テスト・起動](../docs/DEVELOPMENT.md)を参照してください。

実際のsandboxコンテナを使用するテストは、
[Docker統合テスト](./tests/integration/README.md)を参照してください。

## 参考

下記記事を参考にさせていただきました。

- FastAPI + nginx: https://qiita.com/junzai/items/4b737a4fafbe888bc709
