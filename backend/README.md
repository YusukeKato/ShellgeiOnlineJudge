# SHELLGEI ONLINE JUDGE: backend

`backend` directoryには、FastAPIによる公開Web API、内部runner API、
問題の判定、実行ログの保存、sandboxコンテナの管理を行うPythonコードがあります。

## 主な構成

- `main.py`: API endpointとapplication起動・終了処理
- `runner_main.py`: 認証付き内部runnerとsandbox poolの起動・終了処理
- `api/`: API endpoint
- `models/`: APIの入出力、実行ログ、versioned problem schemaのmodel
- `scripts/sandbox_executor.py`: request単位のarchive展開、上限付き出力・artifact取得、
  watchdog、停止、container返却を編成するsandbox実行境界
- `scripts/container_manager.py`: sandbox containerの作成、貸出、破棄、補充を担うpool
- `scripts/`: runner通信、判定、problem schema読込・移行、
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
`RunnerGateway`、`RunnerExecutionRequest`、`RunnerExecutionResponse`と、
`models/execution.py`の`ExecutionResult`を正本とします。requestとresponseは
`protocol_version: 3`を必須とし、
未知version、未知field、欠落field、文字列・画像上限超過を拒否します。

requestは`protocol_version`、`shellgei`、`problem_id`、responseは
`protocol_version`と構造化された`result`で構成します。`result`は`status`、
分離した`stdout`・`stderr`、`exit_code`、`timed_out`、`truncated`、
`duration_ms`、任意の`artifact`・`error`を保持します。
artifactはproblem schemaと一致する`path`、`media_type`、Base64 `data`を保持します。
これは外部公開APIではなく、backendとrunnerを同時に更新する内部protocolです。
公開APIと既存DB logへ渡すときだけ、構造化結果を従来の結合済み表示文字列へ変換します。

公開submission APIは画像dataに加えて`image_media_type`を返します。画像がない場合は
空文字列と`null`、現在の画像問題では`image/jpeg`を返します。frontendはJPEG/GIFだけを
data URLとして許可します。

text判定は`ExecutionResult`から`TextJudgeInput`へ必要項目だけを渡し、
file I/Oを行わないpure functionへ分離しています。判定規則の正本は
[問題データのText判定](../problems/README.md#text判定)を参照してください。

## 参考

下記記事を参考にさせていただきました。

- FastAPI + nginx: https://qiita.com/junzai/items/4b737a4fafbe888bc709
