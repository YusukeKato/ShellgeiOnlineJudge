# 開発環境の構築・テスト・起動

この文書は、開発用PCでShellgeiOnlineJudgeをテストし、Docker Composeで起動するまでの手順を説明します。

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
- Python 3.10以上（コンテナ内の実行環境はPython 3.12）
- Poetry
- Docker Engine、Docker Compose plugin、rootless Docker
- OpenSSL（開発用TLS証明書の生成に使用）

frontendをホスト上で直接検査する場合だけ、Node.js 22とYarnも必要です。
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
- backendの起動処理

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

## 3. リポジトリとPython依存関係

```sh
git clone https://github.com/YusukeKato/ShellgeiOnlineJudge.git
cd ShellgeiOnlineJudge
poetry install
```

Pythonの実行環境を確認します。

```sh
poetry run python --version
poetry run pytest --version
```

## 4. 開発用の環境変数

サンプルをコピーします。`.env`はGit管理対象外であり、Docker build contextからも除外されます。

```sh
cp .env.example .env
id -u
printf '%s\n' "${XDG_RUNTIME_DIR}/docker.sock"
```

`.env`では、少なくとも次の値を開発環境に合わせます。`1000`は実際のUIDへ置き換えてください。

```dotenv
POSTGRES_USER=soj_user
POSTGRES_PASSWORD=開発専用のパスワード
POSTGRES_DB=soj_db
DATABASE_URL=postgresql://soj_user:開発専用のパスワード@db:5432/soj_db

DOCKER_SOCKET_PATH=/run/user/1000/docker.sock

HTTPS_BIND_ADDRESS=127.0.0.1
HTTPS_PORT=8443
TLS_CERTIFICATE_PATH=./deploy/tls/fullchain.pem
TLS_PRIVATE_KEY_PATH=./deploy/tls/privkey.pem

SERVER_URL=https://localhost:8443
EXECUTION_LOG_RETENTION_DAYS=365
EXECUTION_LOG_MAX_ROWS=10000
REACT_APP_SOJ_URL=https://localhost:8443
```

環境変数には次の条件があります。

- `POSTGRES_PASSWORD`と`DATABASE_URL`内のパスワードを一致させる
- URLの予約文字を含むパスワードは、`DATABASE_URL`側でpercent-encodingする
- 実行ログは365日以内かつ最新10,000件以内だけを保持する
- retention値を変更する場合は、どちらも1以上の整数にする

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

### Docker統合テスト

実際にsandboxコンテナを生成・削除します。rootless daemonを明示したうえで実行してください。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
docker pull theoldmoon0602/shellgeibot
SOJ_RUN_DOCKER_TESTS=1 poetry run pytest -m docker
```

全問題の正解コマンドを実行する回帰テストは、追加のフラグを必要とします。

```sh
SOJ_RUN_DOCKER_TESTS=1 SOJ_RUN_FULL_REGRESSION=1 \
  poetry run pytest -m full_regression
```

テスト内容の詳細は[Docker統合テスト](../backend/tests/integration/README.md)を参照してください。

次のような極端な負荷条件を扱う耐性試験は、
日常利用の開発PCや本番ホストで実行しないでください。

- fork bomb
- ディスク枯渇
- Docker daemon停止
- 大量コンテナ生成

これらの試験には、ホスト側watchdogとスナップショット復元手段を備えた
使い捨てVMが必要です。

### frontendをホストで検査する場合

Node.js 22とYarnが利用できる環境で実行します。
依存関係の導入方法は
[Node.js公式ダウンロードページ](https://nodejs.org/en/download/)を参照してください。

```sh
cd frontend
yarn install --frozen-lockfile
yarn format:check
yarn lint
CI=true yarn test --watchAll=false
yarn build
cd ..
```

Composeのfrontendイメージをビルドすることでも、本番用の`yarn build`を確認できます。

## 7. Composeでの起動

rootless daemonへsandboxイメージをpullし、設定検査後に起動します。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
docker pull theoldmoon0602/shellgeibot
./deploy/rootless-compose.sh config --quiet
./deploy/rootless-compose.sh up -d --build
./deploy/rootless-compose.sh ps
```

起動ログを確認します。

```sh
./deploy/rootless-compose.sh logs --tail=100 db backend frontend
./deploy/rootless-compose.sh logs -f backend
```

APIの疎通を確認します。

```sh
curl --insecure https://localhost:8443/api
```

frontend nginxの設定を検査します。

```sh
./deploy/rootless-compose.sh exec frontend nginx -t
```

frontend nginxは、APIへ次の受付制御を適用します。

- request bodyは最大16 KiB
- shell実行APIは接続元IPごとに5 requests/second、burst 5
- shell実行APIは接続元IPごとに同時5 requests
- その他のAPIは接続元IPごとに20 requests/second、burst 40
- その他のAPIは接続元IPごとに同時20 requests
- rateまたは同時request数の超過時は429
- backendからのresponse受信間隔は最大30秒

DB、backend、frontendのDockerログは、`local` logging driverで
各service 10 MiB、3ファイルまでにrotationします。

ブラウザでは`https://localhost:8443`を開きます。

## 8. 停止・再起動

```sh
./deploy/rootless-compose.sh restart backend
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

### backendがsandboxイメージを見つけられない

rootfulとrootlessのイメージは共有されません。rootless socketを指定した同じshellでpullしてください。

```sh
docker pull theoldmoon0602/shellgeibot
docker image inspect theoldmoon0602/shellgeibot
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
