# Docker統合テスト

この文書は、Docker統合テストの実行条件、コマンド、検証範囲の正本です。

通常のbackendテストでは、`docker` markerが付いたテストを除外します。
Docker統合テストは実際のsandboxコンテナを生成・削除するため、
隔離されたrootless Docker環境でのみ実行してください。
本番ホストや共有CI runnerでは実行しないでください。

次のイメージを、rootless daemonへ事前にpullしてください。

```sh
docker pull theoldmoon0602/shellgeibot
docker pull postgres:15-alpine
docker pull nginx:alpine
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
- 動的sandboxのlogging driverが`none`であること
- sandboxの待機PID 1のstdin、stdout、stderrが`/dev/null`であること
- 同じownerの旧sandboxをrunner起動時に回収すること
- root filesystemがread-onlyであること
- 通常ファイルの書き込み先が、容量・inode制限付きの
  `/work`、`/tmp`、`/media`、`/dev`に限定されていること
- 多数の小ファイルと複数の大きなファイルがtmpfs上限を超えられないこと
- working directory、HOME、一時ファイル、入力ファイル、画像問題が動作すること
- 使用済みcontainerの書き込み状態が次のrequestへ残らないこと
- 一時PostgreSQL上で実行ログの期間・件数上限、NUL保存時の正規化、
  lock timeoutとrollback後の再保存が機能すること
- 無出力コマンドのタイムアウト
- Docker execのstdout・stderr分離、非0終了code、所要時間の取得
- コンテナ削除
- 実行中コンテナからの上限付き画像取得
- workerの回復
- 実nginxで、sandboxを開始しないrequestが
  正常requestと共有の実行開始枠を消費しないこと
- 実nginxで、client指定のHostを内部upstream名へ置き換え、
  `Forwarded`、`X-Forwarded-*`、`X-Real-IP`をbackendへ転送しないこと

現在登録されている全問題の回帰テストには、追加の明示指定が必要です。
この回帰ではschema v3の全92問から`reference_solution`を読み、実sandboxで実行します。
runnerとjudgeには起動時検証済みの同じ不変problem repositoryを注入し、fixture、
期待出力、正解画像がrequestごとのfile再読込なしで利用される経路を検証します。
legacy `yaml_data/`とのsemantic一致はnon-Docker testで別途検証します。

```sh
SOJ_RUN_DOCKER_TESTS=1 SOJ_RUN_FULL_REGRESSION=1 \
  poetry run pytest -m full_regression
```

下記のテストは含めません。

- fork bomb
- ホストディスク枯渇
- Docker daemon停止
- 大量コンテナ生成など、極端な負荷条件を扱う耐性試験

これらはホスト側watchdogを備え、スナップショットから復元できる使い捨てVMでのみ実行してください。
