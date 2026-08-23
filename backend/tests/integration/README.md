# Docker統合テスト

通常のbackendテストでは、`docker` markerが付いたテストを除外します。
Docker統合テストは実際のsandboxコンテナを生成・削除するため、
隔離されたrootless Docker環境でのみ実行してください。
本番ホストや共有CI runnerでは実行しないでください。

リポジトリのルートから、rootless socketを指定して実行します。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
SOJ_RUN_DOCKER_TESTS=1 poetry run pytest -m docker
```

テストでは下記を確認します。

- 接続先daemonがrootlessであること
- cgroup v2によるCPU・メモリ・PID制限が実際に反映されていること
- 基本的なDocker隔離設定
- 無出力コマンドのタイムアウト
- コンテナ削除
- 停止済みコンテナからの画像取得
- workerの回復

全92問の回帰テストには、追加の明示指定が必要です。

```sh
SOJ_RUN_DOCKER_TESTS=1 SOJ_RUN_FULL_REGRESSION=1 \
  poetry run pytest -m full_regression
```

`theoldmoon0602/shellgeibot` イメージを、rootless daemonへ事前にpullしてください。

下記のテストは含めません。

- fork bomb
- ホストディスク枯渇
- Docker daemon停止
- 大量コンテナ生成など、極端な負荷条件を扱う耐性試験

これらはホスト側watchdogを備え、スナップショットから復元できる使い捨てVMでのみ実行してください。
