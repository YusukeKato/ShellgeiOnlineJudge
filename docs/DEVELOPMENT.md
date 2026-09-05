# 開発環境の構築・テスト・起動

この文書は、開発用PCでShellgeiOnlineJudgeをテストし、Docker Composeで起動するまでの手順を説明します。
ローカル開発環境とDockerを使用しない検査手順は、この文書を正本とします。

このサービスは、インターネット経由で入力された任意のシェルコマンドを実行します。

開発環境には次の条件を推奨します。

- rootless Dockerを使用する
- 通常ユーザーを`docker`グループへ追加しない
- 日常利用のデータや重要な資格情報を置かない
- 可能であれば専用の開発環境を使用する

rootless Docker自体も完全なsandboxではありません。

## 1. 前提環境

推奨する環境は次のとおりです。

- Linux（systemdとcgroup v2を利用できる環境）
- Git
- Python 3.12、3.13、3.14（production containerはPython 3.12）
- Poetry
- Docker Engine、Docker Compose plugin、rootless Docker
- OpenSSL（開発用TLS証明書の生成に使用）

frontendをホスト上で直接検査する場合だけ、Node.js 22系（22.22.2以上）と
Yarn 1.22.22も必要です。
Composeでビルドするだけなら、ホストへのNode.jsの導入は不要です。

Ubuntu系では、基本ツールを次のように導入できます。

```sh
sudo apt-get update
sudo apt-get install -y git curl python3 python3-venv pipx openssl uidmap
pipx ensurepath
pipx install poetry
```

`pipx ensurepath`の後は、いったんログインし直すか、新しいshellを開いてください。

Docker EngineとCompose pluginは、
[Docker公式のUbuntu向け手順](https://docs.docker.com/engine/install/ubuntu/)で導入してください。

rootless用のスクリプトがない場合は、
Docker公式リポジトリから次のパッケージも導入します。

```sh
sudo apt-get install -y docker-ce-rootless-extras
```

## 2. rootless Dockerの設定

rootless Dockerの詳細とディストリビューション別の前提条件は、
[Docker公式rootless mode手順](https://docs.docker.com/engine/security/rootless/)を参照してください。

まず、現在のユーザーにsubordinate UID/GIDが割り当てられていることを確認します。

```sh
command -v newuidmap
command -v newgidmap
grep "^$(whoami):" /etc/subuid
grep "^$(whoami):" /etc/subgid
```

rootful Docker daemonをこのホストで使用しない場合は、誤接続を防ぐため停止・無効化します。

```sh
sudo systemctl disable --now docker.service docker.socket
```

rootless daemonを通常ユーザーとしてセットアップします。`sudo`を付けないでください。

```sh
dockerd-rootless-setuptool.sh check
dockerd-rootless-setuptool.sh install
systemctl --user enable --now docker
sudo loginctl enable-linger "$(whoami)"
```

現在のshellでrootless socketを使用します。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
docker context use rootless
docker info
```

`docker info`の`Security Options`に`rootless`が表示されることを確認してください。

次の処理もこの条件を検証し、rootful daemonへの接続を拒否します。

- Compose起動用wrapper
- runnerの起動処理

毎回設定する場合は、利用中のshellの設定ファイルへ次の行を追加できます。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
```

### cgroupによる制限の確認

sandboxのCPU、メモリ、PID数を制限するには、rootless Dockerからcgroup v2の各controllerを利用できる必要があります。

```sh
docker info --format 'CgroupDriver={{.CgroupDriver}} CgroupVersion={{.CgroupVersion}}'
cat "/sys/fs/cgroup/user.slice/user-$(id -u).slice/user@$(id -u).service/cgroup.controllers"
```

次の条件を確認してください。

- Dockerがcgroup v2を使用している
- cgroup driverがsystemdである
- controller一覧に`cpu`、`memory`、`pids`が含まれる

controllerが不足する場合は、
[Docker公式rootless modeのTips](https://docs.docker.com/engine/security/rootless/tips/#limiting-resources)に従い、
systemd側のdelegationを設定します。

```sh
sudo install -d -m 755 /etc/systemd/system/user@.service.d
sudoedit /etc/systemd/system/user@.service.d/delegate.conf
```

`delegate.conf`を次の内容にします。

```ini
[Service]
Delegate=cpu cpuset io memory pids
```

設定後はsystemdを再読み込みし、ログインし直してからrootless daemonとcontrollerを再確認します。

```sh
sudo systemctl daemon-reload
systemctl --user restart docker
```

runnerは起動時にcgroup v2とsystemd driverを確認し、
各sandboxへCPU、メモリ、PID数の上限が実際に反映されたことも検査します。
条件を満たさない場合はsandboxを破棄して起動に失敗するため、
起動エラーが発生した場合は上記のdaemon設定とcontroller delegationを確認してください。

## 3. リポジトリとPython依存関係

```sh
git clone https://github.com/YusukeKato/ShellgeiOnlineJudge.git
cd ShellgeiOnlineJudge
poetry install --with e2e
```

Pythonの実行環境を確認します。

```sh
poetry run python --version
poetry run pytest --version
```

依存は共有・backend・runner・開発・旧補助のgroupに分けています。
全体のmypy検査がbrowser scriptも読むため、上記では任意の`e2e` groupを明示して導入します。
PlaywrightのPython packageだけを追加し、ブラウザ本体はホストへinstallしません。
本番imageの収録対象は[backend文書](../backend/README.md#本番runtime-image)を参照してください。

## 4. 開発用の環境変数

環境変数の一覧と既定値は[`.env.example`](../.env.example)を正本とします。
サンプルをコピーします。`.env`はGit管理対象外であり、
Docker build contextからも除外されます。

```sh
cp .env.example .env
id -u
printf '%s\n' "${XDG_RUNTIME_DIR}/docker.sock"
```

`.env`では、少なくとも次の値を開発環境に合わせます。
`1000`は実際のUIDへ置き換えてください。

```dotenv
POSTGRES_PASSWORD=開発専用のパスワード
DATABASE_URL=postgresql://soj_user:開発専用のパスワード@db:5432/soj_db

DOCKER_SOCKET_PATH=/run/user/1000/docker.sock
SANDBOX_OWNER_ID=shellgei-online-judge-development
RUNNER_SHARED_SECRET=64文字のランダム16進数
SERVER_URL=https://localhost:8443
VITE_SOJ_URL=https://localhost:8443
```

### runner用socket groupの設定

`DOCKER_SOCKET_GID`には、rootless container内から見たsocketのGIDを設定します。
ホストでの`stat`のGIDとは一致しない場合があるため、Compose起動前に次の手順で確認します。
先にbuildするrunner imageは検査にも使用します。下記ではsocketの属性だけを読み、
runner serverやsandboxは起動しません。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR:?}/docker.sock"
case "$(docker info --format '{{json .SecurityOptions}}')" in
    *name=rootless*) ;;
    *) echo 'rootless Docker is required' >&2; exit 1 ;;
esac
docker build --file backend/Dockerfile --target runner --tag soj-runner:socket-check .
docker run --rm --network none --user 0:0 --read-only \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,src=${DOCKER_HOST#unix://},dst=/run/docker.sock,readonly" \
  soj-runner:socket-check python -c 'import os; print(os.stat("/run/docker.sock").st_gid)'
```

出力された整数を`.env`の`DOCKER_SOCKET_GID`へ設定してください。
`DOCKER_SOCKET_PATH`も同じsocket pathに合わせます。上の`--user 0:0`は属性読取り用の
一時containerだけに適用し、実際のrunnerはimage既定の非root userで動かします。
daemon移設やUID/GID mappingを変更した場合は再確認します。値が空ならComposeは拒否します。

### 共通する環境変数の条件

開発環境と本番環境に共通する環境変数の条件は次のとおりです。

- `POSTGRES_PASSWORD`と`DATABASE_URL`内のパスワードを一致させる
- `DATABASE_OPERATION_TIMEOUT_SECONDS`は1以上の整数にする
- `RUNNER_SHARED_SECRET`には`openssl rand -hex 32`で生成した値を設定する
- runnerとbackendへ同じ`RUNNER_SHARED_SECRET`が渡される
- `SANDBOX_OWNER_ID`は同じDocker daemon上の他環境と重複させない
- `DOCKER_SOCKET_GID`には上記手順で確認したcontainer内のsocket GIDを設定する
- URLの予約文字を含むパスワードは、`DATABASE_URL`側でpercent-encodingする
- TLS証明書の配置を変える場合は、`TLS_CERTIFICATE_PATH`と
  `TLS_PRIVATE_KEY_PATH`を合わせる

実行ログの保持仕様は、
[SECURITY.mdの「実行ログとDockerログ」](../SECURITY.md#実行ログとdockerログ)を参照してください。

backendは起動時にDBを最新revisionへ自動migrationします。SQLiteを使うforward・rollback・
失敗時のrevision検査は通常の非Docker test、一時PostgreSQLを使うtransactional DDL検査は
Docker統合テストに含まれます。開発DBの現在schemaを明示的にheadへ進める場合は、
対象DBへホストから接続できる`DATABASE_URL`を環境変数に設定し、リポジトリrootから
次を実行します。CLIの接続設定は[backend文書](../backend/README.md#実行ログとdb-migration)を参照してください。

```sh
cd backend
poetry run python -m soj_backend.database_migrations head
cd ..
```

rollback commandと本番backup条件は
[backendの実行ログとDB migration](../backend/README.md#実行ログとdb-migration)を参照してください。

## 5. 開発用TLS証明書

自己署名証明書を、Git管理対象外の`deploy/tls`へ生成します。

```sh
install -d -m 700 deploy/tls
openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 30 \
  -keyout deploy/tls/privkey.pem \
  -out deploy/tls/fullchain.pem \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
chmod 600 deploy/tls/privkey.pem
```

ブラウザでは自己署名証明書の警告が出ます。ローカル開発以外には使用しないでください。

## 6. テスト

### Pythonの静的検査と単体テスト

Dockerを使用しない検査は、リポジトリのルートで実行します。

```sh
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy .
poetry run pytest -m "not docker"
```

CIは、[前提環境](#1-前提環境)に記載したすべてのPython versionで
同じ検査を実行します。
CIの権限・workflow検証・secret/依存/image scan・SBOM・provenanceは
[CIとソフトウェア供給網の検査](./CI.md)を正本とします。

### Docker統合テスト

実行条件、必要なイメージ、コマンド、検証内容は、
[Docker統合テスト](../backend/tests/integration/README.md)を正本とします。
このテストは実際にsandboxコンテナを生成・削除します。
実UI・nginx・backend・runner・DBを通す
[ComposeとブラウザのE2E](../backend/tests/integration/README.md#composeとブラウザのe2e)は、
専用imageのbuildと追加flagが必要です。

次のような極端な負荷条件を扱う耐性試験は、
日常利用の開発PCや本番ホストで実行しないでください。

- fork bomb
- ディスク枯渇
- Docker daemon停止
- 大量コンテナ生成

これらの試験には、ホスト側watchdogとスナップショット復元手段を備えた
使い捨てVMが必要です。

### frontendをホストで検査する場合

Node.js 22系（22.22.2以上）とYarn 1.22.22が利用できる環境で実行します。
依存関係の導入方法は
[Node.js公式ダウンロードページ](https://nodejs.org/en/download/)を参照してください。

```sh
cd frontend
yarn install --frozen-lockfile
yarn format:check
yarn lint
yarn typecheck
yarn test
yarn build
cd ..
```

Composeのfrontendイメージをビルドすることでも、本番用の`yarn build`を確認できます。

## 7. Composeでの起動

rootless daemonへsandboxイメージをpullし、設定検査後に起動します。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
docker pull \
  theoldmoon0602/shellgeibot:latest@sha256:aaaa5b10e6419e4309a0b53a8d9e48ddcadabb92cc1dc7e1a739bc0248741a36
./deploy/rootless-compose.sh config --quiet
./deploy/rootless-compose.sh up -d --build
./deploy/rootless-compose.sh ps
```

起動ログを確認します。

```sh
./deploy/rootless-compose.sh logs --tail=100 db runner backend frontend
./deploy/rootless-compose.sh logs -f runner backend
```

APIの疎通を確認します。

```sh
curl --insecure https://localhost:8443/api
```

frontend nginxの設定を検査します。

```sh
./deploy/rootless-compose.sh exec frontend nginx -t
```

frontend nginxの現在のHTTP制約とDockerログの上限は、
[SECURITY.mdの「ネットワークとHTTPの制約」](../SECURITY.md#ネットワークとhttpの制約)と
[「実行ログとDockerログ」](../SECURITY.md#実行ログとdockerログ)を参照してください。

ブラウザでは`https://localhost:8443`を開きます。

## 8. 停止・再起動

```sh
./deploy/rootless-compose.sh restart backend
./deploy/rootless-compose.sh restart runner
./deploy/rootless-compose.sh stop
./deploy/rootless-compose.sh start
./deploy/rootless-compose.sh down
```

通常の停止では`down -v`を実行しないでください。
`-v`を付けるとPostgreSQLの名前付きvolumeも削除され、DBデータを失います。

## 9. よくある問題

### rootful daemonへの接続エラー

`DOCKER_HOST`と`.env`の`DOCKER_SOCKET_PATH`を確認します。

```sh
printf '%s\n' "${DOCKER_HOST:-未設定}"
printf '%s\n' "${XDG_RUNTIME_DIR}/docker.sock"
docker info --format '{{json .SecurityOptions}}'
```

### runnerがsandboxイメージを見つけられない

rootfulとrootlessのイメージは共有されません。rootless socketを指定した同じshellでpullしてください。

```sh
docker pull \
  theoldmoon0602/shellgeibot:latest@sha256:aaaa5b10e6419e4309a0b53a8d9e48ddcadabb92cc1dc7e1a739bc0248741a36
docker image inspect \
  theoldmoon0602/shellgeibot:latest@sha256:aaaa5b10e6419e4309a0b53a8d9e48ddcadabb92cc1dc7e1a739bc0248741a36
```

### TLSファイルのmountに失敗する

`.env`のパスとファイル権限を確認します。

```sh
ls -l deploy/tls/fullchain.pem deploy/tls/privkey.pem
./deploy/rootless-compose.sh config
```

### Docker統合テストだけ失敗する

rootless判定とcgroup controllerを再確認してください。

Unix socket接続が制限される環境では、rootless Dockerがホストで動作していても
Docker統合テストを実行できないことがあります。
通常のCodex filesystem sandboxもこの制限に該当します。
