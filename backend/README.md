# SHELLGEI ONLINE JUDGE: backend

`backend` directoryには、FastAPIによる公開Web API、内部runner API、
問題の判定、実行ログの保存、sandboxコンテナの管理を行うPythonコードがあります。

## 主な構成

- `main.py`: API endpointとapplication起動・終了処理
- `runner_main.py`: 認証付き内部runnerとsandbox poolの起動・終了処理
- `api/`: API endpoint
- `models/`: APIの入出力、実行ログ、versioned problem schemaのmodel
- `scripts/`: runner通信、Docker実行、判定、problem schema読込・移行、
  起動時検証済みの不変problem repository、入力検証、DB接続とrollback-safeな
  実行ログ保存・保持処理
- `tests/`: 単体・API・Docker統合テスト

## 開発とテスト

環境構築、Pythonの静的検査、単体テストは、
[開発環境の構築・テスト・起動](../docs/DEVELOPMENT.md)を参照してください。

実際のsandboxコンテナを使用するテストは、
[Docker統合テスト](./tests/integration/README.md)を参照してください。

problem schema、manifest revision、移行・更新手順は、
[問題データ](../problems/README.md)を参照してください。

## 内部runner protocol

backendからrunnerへの実行境界は、`scripts/runner_protocol.py`の
`RunnerGateway`、`RunnerExecutionRequest`、`RunnerExecutionResponse`、
`ExecutionResult`を正本とします。requestとresponseは`protocol_version: 1`を必須とし、
未知version、未知field、欠落field、文字列・画像上限超過を拒否します。

requestは`protocol_version`、`shellgei`、`problem_id`、responseは
`protocol_version`と、`output`・`image`を持つ`result`で構成します。
これは外部公開APIではなく、backendとrunnerを同時に更新する内部protocolです。
exit code、stderr、timeout、artifact等の追加実行情報は、後続のstructured execution
outcomeで`ExecutionResult`へ追加します。

text判定は`JudgeResult`と`TextJudgeInput`を型付き境界とし、file I/Oやrepository参照を
行わないpure functionへ分離しています。判定規則の正本は
[問題データのText判定](../problems/README.md#text判定)を参照してください。

## 参考

下記記事を参考にさせていただきました。

- FastAPI + nginx: https://qiita.com/junzai/items/4b737a4fafbe888bc709
