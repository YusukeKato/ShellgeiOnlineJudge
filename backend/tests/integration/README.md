# Docker統合テスト

この文書は、Docker統合テストの実行条件、コマンド、検証範囲の正本です。

通常のbackendテストでは、`docker` markerが付いたテストを除外します。
Docker統合テストは実際のsandboxコンテナを生成・削除するため、
隔離されたrootless Docker環境でのみ実行してください。
本番ホストや共有CI runnerでは実行しないでください。

次のイメージを、rootless daemonへ事前にpullしてください。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
docker pull \
  theoldmoon0602/shellgeibot:latest@sha256:aaaa5b10e6419e4309a0b53a8d9e48ddcadabb92cc1dc7e1a739bc0248741a36
docker pull \
  postgres:15-alpine@sha256:fe0737ba566a2c5b2a28f34433c0a423261900ec17b9bf7ad115e1aae7e57f1b
docker pull \
  nginx:alpine@sha256:db35bfc6b2951e7f8a72db5db120288c127ffaeeb4a6d4b95a26fead017d5913
```

リポジトリのルートから、rootless socketを指定して実行します。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
SOJ_RUN_DOCKER_TESTS=1 poetry run pytest -m docker
```

テストでは下記を確認します。

- 接続先daemonがrootlessであること
- cgroup v2によるCPU・メモリ・PID制限が実際に反映されていること
- 基本的なDocker隔離設定
- sandbox imageの`VOLUME`宣言がなく、実containerに予期しないmountがないこと
- 動的sandboxのlogging driverが`none`であること
- sandboxの待機PID 1のstdin、stdout、stderrが`/dev/null`であること
- 同じownerの旧sandboxをrunner起動時に回収すること
- root filesystemがread-onlyであること
- 通常ファイルの書き込み先が、容量・inode制限付きの
  `/work`、`/tmp`、`/media`、`/dev`に限定されていること
- 多数の小ファイルと複数の大きなファイルがtmpfs上限を超えられないこと
- working directory、HOME、一時ファイル、入力ファイル、画像問題が動作すること
- 使用済みcontainerの書き込み状態が次のrequestへ残らないこと
- 一時PostgreSQL上でlegacy DBからのforward migration、構造化列のrollback、
  migration失敗時のtransactional DDL rollbackが機能すること
- `ExecutionLogRepo`による期間・件数上限、NUL保存時の正規化、
  lock timeoutとrollback後の再保存が機能すること
- 無出力コマンドのタイムアウト
- Docker execのstdout・stderr分離、非0終了code、所要時間の取得
- コンテナ削除
- 実行中コンテナからの上限付き画像取得
- workerの回復
- 実nginxで、sandboxを開始しないrequestが
  正常requestと共有の実行開始枠を消費しないこと
- 実nginxで、client指定のHostを内部upstream名へ置き換え、
  [HTTPの制約](../../../SECURITY.md#ネットワークとhttpの制約)で指定したforwarded headerを
  backendへ転送しないこと

現在登録されている全問題の回帰テストには、追加の明示指定が必要です。
この回帰ではschema v3の全92問から`reference_solution`を読み、実sandboxで実行します。
runnerとjudgeには起動時検証済みの同じ不変problem repositoryを注入し、fixture、
期待出力、正解画像がrequestごとのfile再読込なしで利用される経路を検証します。
legacy `yaml_data/`とのsemantic一致はnon-Docker testで別途検証します。

```sh
SOJ_RUN_DOCKER_TESTS=1 SOJ_RUN_FULL_REGRESSION=1 \
  poetry run pytest -m full_regression
```

## 本番runtime imageの検証

`test_runtime_images.py`は追加の明示flagと、検証対象としてbuild済みの2つのimageを
必要とします。上記のrootless環境を確認したうえで、リポジトリrootから実行します。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
docker build --file backend/Dockerfile --target backend --tag soj-backend:runtime-test .
docker build --file backend/Dockerfile --target runner --tag soj-runner:runtime-test .
SOJ_RUN_DOCKER_TESTS=1 SOJ_RUN_RUNTIME_IMAGE_TESTS=1 \
  SOJ_BACKEND_RUNTIME_IMAGE=soj-backend:runtime-test \
  SOJ_RUNNER_RUNTIME_IMAGE=soj-runner:runtime-test \
  poetry run pytest backend/tests/integration/test_runtime_images.py
```

実imageの非root起動、不要package・逆側コードの不在、問題data読込、socket補助groupの
必要性を確認します。一時的なbackend・runner・PostgreSQLを内部networkへ配置し、
Composeと同じ実行制限でtext/image判定とDB保存まで検証します。test ownerだけの
sandbox・container・networkを終了時に回収し、本番volumeや公開portは使用しません。
frontend/nginx、browser、Compose全体の起動・障害回復E2EはR3-024の対象です。

## 対象外の耐性試験

下記のテストは含めません。

- fork bomb
- ホストディスク枯渇
- Docker daemon停止
- 大量コンテナ生成など、極端な負荷条件を扱う耐性試験

これらはホスト側watchdogを備え、スナップショットから復元できる使い捨てVMでのみ実行してください。
