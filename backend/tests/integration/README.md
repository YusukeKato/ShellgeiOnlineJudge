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
  nginx:alpine@sha256:72ba65eb42c10344912a84ff42408db7d34f2feb642204570ab8fc5ffd29f1d3
docker build --file deploy/postgres/Dockerfile --tag soj-db:local .
```

DBの実行にはbuild済みの派生imageを使用します。`SOJ_DB_IMAGE`で上書きでき、省略時は
本番Composeのimage名を使用します。公式PostgreSQLのpullは既存volume互換性testの移行元用です。
`test_postgres_image.py`は専用volumeで旧image→派生image→旧imageの読み書き、
非rootのPID 1、正常停止とdata保持を確認します。本番volumeには接続しません。

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
- ホスト監視CLIが別ownerを除外し、runner停止・削除後のsandbox残存を読み取りだけで検出すること
  （`test_sandbox_health_docker.py`。runtime image検査の有効化とbuild済みbackend imageが必要）
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

実imageのPython・Expat修正版、非rootでの共有・専用package全moduleのimport、
開発tool・逆側package・runner側Pillowの不在、問題data読込、socket補助groupの
必要性を確認します。一時的なbackend・runner・PostgreSQLを内部networkへ配置し、
Composeと同じ実行制限でtext/image判定とDB保存まで検証します。test ownerだけの
sandbox・container・networkを終了時に回収し、本番volumeや公開portは使用しません。
frontend/nginxとbrowserを含む検証は、次のCompose E2Eで行います。

## ComposeとブラウザのE2E

`test_database_roles.py`は専用の一時PostgreSQLで旧行・所有者を維持したrole分離、保存・retention、
DDL・migration表更新・採番変更・role昇格の拒否、権限の後付け検知とrollback/re-upgradeを検証します。

`test_compose_e2e.py`は実際の`docker-compose.yml`を読み込み、rootless確認wrapperで
frontend/nginx、backend、runner、PostgreSQLを起動します。DB起動後に同じbackend imageの
一時`migrate` serviceでschemaと専用app roleを準備し、通常用credentialだけをbackendへ渡します。上記と同じ隔離環境でのみ
実行してください。Docker Compose v2以降、`openssl`、DB・browserを含むbuild済みの5つのtest imageが必要です。
ホストのbrowserやNode.jsは使用しません。

リポジトリrootで、現在のコードから検証対象をbuildします。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
docker info --format '{{json .SecurityOptions}}'  # name=rootlessを確認する
docker build --file backend/Dockerfile --target backend --tag soj-backend:compose-test .
docker build --file backend/Dockerfile --target runner --tag soj-runner:compose-test .
docker build --file frontend/Dockerfile --build-arg VITE_SOJ_URL= --tag soj-frontend:compose-test .
docker build --file backend/tests/integration/browser/Dockerfile --tag soj-browser:compose-test .
docker build --file deploy/postgres/Dockerfile --tag soj-db:compose-test .

export SOJ_DB_IMAGE=soj-db:compose-test
export SOJ_COMPOSE_BACKEND_IMAGE=soj-backend:compose-test
export SOJ_COMPOSE_RUNNER_IMAGE=soj-runner:compose-test
export SOJ_COMPOSE_FRONTEND_IMAGE=soj-frontend:compose-test
export SOJ_COMPOSE_BROWSER_IMAGE=soj-browser:compose-test
SOJ_RUN_DOCKER_TESTS=1 SOJ_RUN_COMPOSE_E2E=1 \
  poetry run pytest -m compose_e2e
```

`VITE_SOJ_URL`の空文字は同一originを使用するためのtest build設定です。
frontendはloopbackの動的portだけへ公開し、DBのhost portは公開しません。
testはimageをpull/buildせず、指定されたimage IDを使います。通常のDocker統合testでは
`SOJ_RUN_COMPOSE_E2E`未指定によりskipされます。Compose経路の全問題回帰も実行する場合は、
上記のimage環境変数を維持して、追加flagを指定します。

```sh
SOJ_RUN_DOCKER_TESTS=1 SOJ_RUN_COMPOSE_E2E=1 SOJ_RUN_FULL_REGRESSION=1 \
  poetry run pytest -m compose_e2e
```

検証内容:

- TLS nginxの静的配信・CSP・問題一覧と、public v3 APIの正解、不正解、timeout、出力上限、画像判定
- 応答header、保存IDと最小権限の通常roleによるPostgreSQLの実保存行の一致
- 内部network経由のrunner認証失敗・problem revision不一致と、実行前の拒否
- test DB停止中の判定保持と`persistence: unavailable`、DB復帰後の再保存と停止前の行の保持
- test runner停止中の503、SIGKILL後の明示再起動による旧sandbox回収、再提出の成功
- runner PID 1のSIGTERM終了後に、Composeのrestart policyで自動再起動して受付が復帰すること
- Chromiumから実UIを操作し、正解・不正解・timeout・出力上限・画像の表示とDB保存を確認
- 追加flag有効時は、全manifest問題の参照解答をnginxから提出し、判定・DB保存まで確認

Docker経由のkillは手動停止として扱われるため、強制終了後の回収と自動再起動は
別の経路として検証します。runner停止中に独立reaperがsandboxを回収する保証は追加しません。
その制約は[SOJ-002](../../../docs/security/README.md#soj-002-runner-crash後の独立した期限強制)へ残します。

testは`soj-e2e-<UUID>`のproject、container名、owner label、DB volume、networkを使用します。
呼出元の`.env`やDB接続情報は継承せず、専用の秘密鍵・共有secret・DB passwordを生成します。
rootless namespace内のsocket GIDを実測し、runnerだけへsocketと補助groupを渡します。
本番のreadonly、capability、tmpfs、logging、service間network制約は維持します。
browser containerはfrontend側networkだけに接続し、socketやDB credentialを持ちません。

正常終了・assert失敗・通常の中断では、service停止と`down --volumes`を試みた後に
当該ownerのsandboxを回収し、専用Compose資源とsandboxの残存がないことを検査します。
回収に成功したら一時credential・証明書fileも削除します。
停止・回収の1段階が失敗しても、残るcleanupを試みます。pytest自身のSIGKILLやhost停止では
finallyを実行できないため、残ったproject名を確認し、そのprojectの生成済み`compose.yml`と
`test.env`を指定してrootless wrapperの`down --volumes`を実行してください。
その後、`com.shellgei-online-judge.owner=<同じproject名>` labelが一致するsandboxだけを確認・削除します。
他projectを巻き込むpruneは使用しません。

ブラウザ専用Dockerfileは、lock済みの任意`e2e` groupと、それに対応するChromiumを導入します。
本番targetや通常の`poetry install`にはこのgroupを含めません。
browser scriptも実際のPlaywright型情報で検査する場合は`poetry install --with e2e`を実行します。
browser本体のホストへのinstallは不要です。構築方法の参考は
[PlaywrightのDocker文書](https://playwright.dev/python/docs/docker)です。

## 対象外の耐性試験

下記のテストは含めません。

- fork bomb
- ホストディスク枯渇
- Docker daemon停止
- 大量コンテナ生成など、極端な負荷条件を扱う耐性試験

これらはホスト側watchdogを備え、スナップショットから復元できる使い捨てVMでのみ実行してください。
