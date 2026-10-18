# 開発環境の構築・テスト・起動

開発用PCでの準備、Dockerを使わない検査、Compose起動、変更の反映はこの文書を正本とします。
API・問題・隔離の仕様はそれぞれの正本を参照し、ここでは作業に必要な順序を説明します。

## 目的別の入口

| 行いたいこと | 必要な準備と読む順序 |
| --- | --- |
| Pythonを検査する | [前提環境](#前提環境) → [リポジトリの取得](#リポジトリの取得) → [ホストでの検査](#ホストでの検査)のPython各節。Docker・DB・TLSは不要 |
| frontendを検査する | [前提環境](#前提環境) → [リポジトリの取得](#リポジトリの取得) → [frontendの検査](#frontendをホストで検査する場合)。Python・Docker・DB・TLSは不要 |
| 全体を起動する | [前提環境](#前提環境) → [リポジトリの取得](#リポジトリの取得) → [rootless設定](#rootless-dockerの設定) → [環境変数](#開発用の環境変数) → [TLS](#開発用tls証明書) → [Compose起動](#composeでの起動) |
| コードや問題を変更する | 対象の[backend](../backend/README.md)・[frontend](../frontend/README.md)・[作問ガイド](./problem-authoring.md) → [変更の反映](#変更を反映する) → [変更別の検査](#変更内容に応じた検査) |
| Dockerを使って検証する | [Docker統合テスト](#docker統合テスト) → 統合テスト文書の検査選択表と実行条件 |

Compose・sandboxを実行する場合はrootless Dockerが必須です。通常ユーザーを`docker`グループへ追加せず、
提出コマンドをホストやbackendのshellで実行しないでください。
任意のシェルコマンドを扱うため、日常利用のデータや重要な資格情報を置かない専用の開発環境を推奨します。
rootless Docker自体も完全なsandboxではありません。[保証範囲と限界](../SECURITY.md)を確認してください。

<a id="1-前提環境"></a>

## 前提環境

以下は用途ごとの要件です。実行するコマンドの作業directoryは、特記がなければリポジトリのルートです。
Compose・rootlessの手順はLinuxのshellで実行します。

| 用途 | 必要な環境 |
| --- | --- |
| 共通 | Git |
| ホストでPythonを検査 | Python 3.12・3.13・3.14のいずれか、Poetry |
| ホストでfrontendを検査 | Node.js 22系（22.22.2以上）、Yarn 1.22.22 |
| Compose起動・Docker統合検査 | Linux（systemd・cgroup v2）、Docker Engine・Compose plugin・rootless Docker、OpenSSL |

Composeでbuildするだけなら、ホストへのPython開発環境・Poetry・Node.js・Yarnの導入は不要です。
production containerのPythonは3.12です。

Ubuntu系で必要な基本ツールを導入する例です。検査だけなら利用しないツールの導入は不要です。

```sh
sudo apt-get update
sudo apt-get install -y git curl python3 python3-venv pipx openssl uidmap
pipx ensurepath
pipx install poetry
```

`pipx ensurepath`の後は、新しいshellを開いてください。ディストリビューション既定の`python3`が
対応versionとは限りません。`python3 --version`で確認し、対応版を用意してから
[Poetryで使用するPythonを選択](#python環境の準備)します。

Node.jsの導入は[公式ダウンロードページ](https://nodejs.org/en/download/)を参照してください。
Yarnの固定と確認は[frontendの検査](#frontendをホストで検査する場合)で行います。

Docker EngineとCompose pluginは[Docker公式のUbuntu向け手順](https://docs.docker.com/engine/install/ubuntu/)で導入してください。
rootless用スクリプトがない場合は、Docker公式リポジトリから次も導入します。

```sh
sudo apt-get install -y docker-ce-rootless-extras
```

## リポジトリの取得

```sh
git clone https://github.com/YusukeKato/ShellgeiOnlineJudge.git
cd ShellgeiOnlineJudge
```

既に取得済みなら、その作業treeを使います。既存の未コミット差分を保持し、無関係な変更を破棄しないでください。

<a id="6-テスト"></a>

## ホストでの検査

Docker・起動用.env・DB・TLSの準備は不要です。

<a id="3-リポジトリとpython依存関係"></a>

### Python環境の準備

対応するPythonを明示して依存を導入します。次はPython 3.12の例です。
3.13・3.14を使う場合は実際の実行file名へ読み替えてください。

```sh
python3.12 --version
poetry env use python3.12
poetry install --with e2e
```

Pythonの実行環境を確認します。

```sh
poetry run python --version
poetry run pytest --version
```

依存は共有・backend・runner・開発のgroupに分けています。
全体のmypy検査がbrowser scriptも読むため、上記では任意の`e2e` groupを明示して導入します。
PlaywrightのPython packageだけを追加し、ブラウザ本体はホストへinstallしません。
本番imageの収録対象は[backend文書](../backend/README.md#本番runtime-image)を参照してください。

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
Ruffのlint対象は`pyproject.toml`の`lint.select`に明記しています。
Ruff本体の更新で検査範囲が意図せず増えないよう、従来の`E4`・`E7`・`E9`・`F`を維持します。
新しいルールの導入は、必要なコード修正と合わせて別途レビューします。
pytestの収集時はtest専用のmemory SQLite URLを明示し、ホストのDB設定を引き継ぎません。
実PostgreSQLを使用するtestは専用fixtureで接続先を準備します。
CIの権限・workflow検証・secret/依存/image scan・SBOM・provenanceは
[CIとソフトウェア供給網の検査](./CI.md)を正本とします。

問題追加のみの場合のローカル検証とCIの分担は、[問題作成ガイド](./problem-authoring.md#作成・検証の進め方)を参照してください。
WSL検証のために作業treeの改行を一時変換する場合は、復元処理とDocker検査を並列実行しないでください。
LFの検証用checkoutを使うか、変換・検査・復元を直列化し、既存差分を保護します。

### frontendをホストで検査する場合

Node.js 22系（22.22.2以上）とYarn 1.22.22が利用できる環境で実行します。
Corepackが利用できる環境では、CIと同じ方法でYarnを固定できます。
Corepackが見つからない場合は、利用中のNode.js環境の導入方法を確認してから進め、version確認を省略しないでください。

```sh
cd frontend
node --version
corepack --version
corepack enable
corepack prepare yarn@1.22.22 --activate
yarn --version
yarn install --frozen-lockfile
yarn format:check
yarn lint
yarn typecheck
yarn test
yarn build
cd ..
```

Composeのfrontendイメージをビルドすることでも、本番用の`yarn build`を確認できます。

UIの起動・API接続の案内は[frontend文書](../frontend/README.md#開発とテスト)を参照してください。

<a id="2-rootless-dockerの設定"></a>

## rootless Dockerの設定

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

<a id="4-開発用の環境変数"></a>

## 開発用の環境変数

設定名・例・既定値は[`.env.example`](../.env.example)を正本とします。
初回だけサンプルをコピーします。既存の`.env`は上書きせず必要な項目だけ編集します。`.env`はGit管理対象外であり、
Docker build contextからも除外されます。

```sh
(
  set -eu
  test ! -e .env
  test ! -L .env
  umask 077
  cp .env.example .env
)
id -u
printf '%s\n' "${XDG_RUNTIME_DIR}/docker.sock"
```

`.env`では、少なくとも次の値を開発環境に合わせます。
`1000`は実際のUIDへ置き換えてください。

```dotenv
POSTGRES_PASSWORD=管理専用のパスワード
MIGRATION_DATABASE_URL=postgresql://soj_user:管理専用のパスワード@db:5432/soj_db
DATABASE_URL=postgresql://soj_app:通常実行専用の別パスワード@db:5432/soj_db

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

設定名・既定値は[`.env.example`](../.env.example)、この節は開発・本番の共通条件、
本番固有の設定は[本番手順](./PRODUCTION.md#本番用の設定)を正本とします。
共通条件は次のとおりです。

- `POSTGRES_USER`・`POSTGRES_PASSWORD`と`MIGRATION_DATABASE_URL`の管理資格情報を一致させる
- `DATABASE_URL`は別の専用ユーザー・別passwordとし、両URLは同じhost・port・DBを指す
- backendの`DATABASE_URL`に既定値はない。Compose外でも明示し、未設定・空・空白だけなら起動を拒否する。URL/driver初期化失敗時は資格情報を含まない固定の診断を出す
- 管理CLIは明示的なPostgreSQL URL（`postgresql`または`postgresql+psycopg2`）を要求し、query optionを受け付けない
- 通常用role名は小文字英字またはunderscoreで始まる小文字英数字/underscoreの63文字以内とし、`pg_`で始めない
- `DATABASE_OPERATION_TIMEOUT_SECONDS`は1以上の整数にする
- `RUNNER_SHARED_SECRET`には`openssl rand -hex 32`で生成した値を設定する
- runnerとbackendへ同じ`RUNNER_SHARED_SECRET`が渡される
- `SANDBOX_IMAGE_ID`は[開発用sandboxのbuildとID保存](#composeでの起動)に従って設定する
- `SANDBOX_OWNER_ID`は同じDocker daemon上の他環境と重複させない
- `DOCKER_SOCKET_GID`には上記手順で確認したcontainer内のsocket GIDを設定する
- URLの予約文字を含むパスワードは、両DB URL側でpercent-encodingする
- TLS証明書の配置を変える場合は、`TLS_CERTIFICATE_PATH`と
  `TLS_PRIVATE_KEY_PATH`を合わせる

実行ログの保持仕様は、
[SECURITY.mdの「実行ログとDockerログ」](../SECURITY.md#実行ログとdockerログ)を参照してください。

backendはDBを自動migrationせず、準備済みschemaと通常実行roleを起動時に検証します。
ComposeのDBは内部networkだけで使用し、loopbackを含むhost portへ公開しません。
管理方法は次の手順を使用してください。

CLIと権限設定の契約は[backendの実行ログとDB migration](../backend/README.md#実行ログとdb-migration)、
既存環境の移行・rollbackは[本番運用](./PRODUCTION.md#更新デプロイ)を参照してください。

### DBへの管理アクセス

ComposeのDB管理は、起動済みDBに対して一時的な管理serviceを実行します。
backend/frontendを停止してからmigrationとrole設定を行い、成功時だけ再開します。
初回起動を含む順序は後述の[Compose起動](#7-composeでの起動)を参照してください。

```sh
./deploy/rootless-compose.sh run --rm --no-deps migrate
```

SQLによる調査にはDBコンテナ内のclientを使用します。hostへのport公開は不要です。

```sh
./deploy/rootless-compose.sh exec db sh -c 'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Composeと別に用意した開発DBへホストのPythonから接続する場合は、そのDBへ到達できる
明示URLを環境変数へ設定します。`.env`はPythonから自動読込されません。
通常backendには通常用`DATABASE_URL`、管理CLIには両URLが必要です。

```sh
PYTHONPATH=backend poetry run python -m soj_backend.database_admin head
```

<a id="5-開発用tls証明書"></a>

## 開発用TLS証明書

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

<a id="7-composeでの起動"></a>

## Composeでの起動

rootless daemonで独自sandboxをbuildし、immutable IDを指定して起動します。
各手順が成功したことを確認してから次へ進みます。収録内容は[sandbox文書](../deploy/sandbox/README.md)を参照してください。

### sandbox imageのbuildとID保存

```sh
(
  set -eu
  export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
  docker build --file deploy/sandbox/Dockerfile --tag soj-sandbox:local .
  docker image inspect soj-sandbox:local --format '{{.Id}}'
)
```

表示された`sha256:...`を`.env`の`SANDBOX_IMAGE_ID`へ保存してください。exportだけでは新しいshellに残りません。
過去のexport値は`.env`より優先されるため、このshellの値を解除して保存した設定を使います。

```sh
unset SANDBOX_IMAGE_ID
```

### DBとサービスの起動

設定を確認し、DBの準備が完了してからmigrationと起動へ進みます。

```sh
(
  set -eu
  ./deploy/rootless-compose.sh config --quiet
  ./deploy/rootless-compose.sh --profile maintenance build
  ./deploy/rootless-compose.sh up -d db
  ./deploy/rootless-compose.sh exec db sh -c 'pg_isready -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
  ./deploy/rootless-compose.sh run --rm --no-deps migrate
  ./deploy/rootless-compose.sh up -d
  ./deploy/rootless-compose.sh ps
)
```

DBがまだ準備中なら`pg_isready`で処理が止まります。`accepting connections`（終了0）になるまで
同じ確認コマンドで待ち、成功後にmigration以降を実行してください。

起動ログを確認します。

```sh
./deploy/rootless-compose.sh logs --tail=100 db runner backend frontend
./deploy/rootless-compose.sh logs -f runner backend
```

APIの疎通を確認します。

```sh
curl --fail --show-error --insecure https://localhost:8443/api
```

frontend nginxの設定を検査します。

```sh
./deploy/rootless-compose.sh exec frontend nginx -t
```

frontend nginxの現在のHTTP制約とDockerログの上限は、
[SECURITY.mdの「ネットワークとHTTPの制約」](../SECURITY.md#ネットワークとhttpの制約)と
[「実行ログとDockerログ」](../SECURITY.md#実行ログとdockerログ)を参照してください。

ブラウザでは`https://localhost:8443`を開きます。

## 変更を反映する

まず対象の責務と仕様を確認します。公開APIは[API仕様](./API.md)、問題は[作問ガイド](./problem-authoring.md)・
[問題データ](../problems/README.md)、Docker・隔離・上限の変更は[SECURITY.md](../SECURITY.md)が入口です。
入力検証 → runner実行 → 判定 → DB保存のどこを変更するかを[backendの構成](../backend/README.md)で確認し、
再現条件と必要な検査を決めます。作業・文書同期・commitの規約は[AGENTS.md](../AGENTS.md)に従います。

| 変更対象 | 起動済み環境への反映で必要なこと |
| --- | --- |
| 文書のみ | サービスのbuild・再起動は不要 |
| frontendのコード・nginx・`VITE_*` | frontendを再buildし、コンテナを再作成。`VITE_*`はbuild時に埋め込まれる公開値 |
| backendのコード | backendとmigrateの両serviceを再build。DB更新がある場合は管理手順に従い、backendを再作成 |
| runnerのコード | runnerを再build・再作成し、readinessを確認 |
| `soj_shared`・問題YAML・画像・manifest・内部protocol | backendとrunnerへ同じ更新を反映。内部protocolの混在とproblem revision不一致を許容しない |
| sandboxのDockerfile・収録ツール・参照data | 検証したsandboxをbuildし、immutable IDを`.env`へ保存してrunnerを再作成 |
| 依存・Compose・環境変数 | 影響するimageを再buildし、設定を反映してコンテナを再作成。DB管理・隔離条件も再確認 |

ComposeはコードをimageへCOPYし、ソースをbind mountしていません。
Git更新・build・`restart`だけでは稼働コンテナが新しいimageへ置き換わりません。

初回起動済みでDBが稼働している開発環境では、次の共通手順でコード・設定を反映できます。
sandboxを変更した場合は先に[buildとID保存](#sandbox-imageのbuildとid保存)を済ませます。
各コマンドが成功したことを確認してから次へ進み、migration失敗時は起動へ進まないでください。

```sh
(
  set -eu
  ./deploy/rootless-compose.sh config --quiet
  ./deploy/rootless-compose.sh --profile maintenance build
  ./deploy/rootless-compose.sh stop frontend backend runner
  ./deploy/rootless-compose.sh run --rm --no-deps migrate
  ./deploy/rootless-compose.sh up -d
  ./deploy/rootless-compose.sh ps
)
```

既存DBのrole・schema変更の注意は[DB管理](../backend/README.md#実行ログとdb-migration)を参照してください。
この手順はDB volumeを削除しません。反映後は[起動時と同じ疎通確認](#composeでの起動)に加え、変更箇所の動作を確認します。

## 変更内容に応じた検査

| 変更対象 | ローカルで確認する範囲 |
| --- | --- |
| Python | [静的検査と非Dockerテスト](#pythonの静的検査と単体テスト)を一式実行 |
| frontend | [format・lint・typecheck・test・build](#frontendをホストで検査する場合)を一式実行 |
| 問題data | [作問ガイドの検証分担](./problem-authoring.md#作成・検証の進め方)に従い、独立期待値・参照解・別解・誤答・境界条件を確認 |
| Docker実行・sandbox・画像回収 | 基本検査に加え、[統合テストの選択表](../backend/tests/integration/README.md)から変更に対応する検査を選択 |
| DB管理・保存 | 関連非Dockerテストと、専用PostgreSQLを使うDocker統合検査 |
| Compose | rootless daemonを明示し、`./deploy/rootless-compose.sh config --quiet`。必要に応じCompose/browser E2E |
| 文書のみ | コードとの整合、相対リンク・見出し、コマンドの作業directory・前提・失敗時の停止条件を確認 |

実施した検査、skip・未実施の理由と未確認範囲を報告し、関連する文書とdiffをレビューに残します。
CI・公開前確認は[CI文書](./CI.md)・[リリース手順](./RELEASE.md)を参照してください。

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

<a id="8-停止・再起動"></a>

## 停止・再起動

restartは同じimage・設定のサービスを再起動する操作です。変更の反映には[再buildと再作成](#変更を反映する)を行います。

```sh
./deploy/rootless-compose.sh restart backend
./deploy/rootless-compose.sh restart runner
./deploy/rootless-compose.sh stop
./deploy/rootless-compose.sh start
./deploy/rootless-compose.sh down
```

通常の停止では`down -v`を実行しないでください。
`-v`を付けるとPostgreSQLの名前付きvolumeも削除され、DBデータを失います。

<a id="9-よくある問題"></a>

## よくある問題

### rootful daemonへの接続エラー

`DOCKER_HOST`と`.env`の`DOCKER_SOCKET_PATH`を確認します。

```sh
printf '%s\n' "${DOCKER_HOST:-未設定}"
printf '%s\n' "${XDG_RUNTIME_DIR}/docker.sock"
docker info --format '{{json .SecurityOptions}}'
```

### runnerがsandboxイメージを見つけられない

rootfulとrootlessのイメージは共有されません。rootless socketを指定した同じshellでbuildし、設定したIDが存在することを確認してください。

```sh
docker build --file deploy/sandbox/Dockerfile --tag soj-sandbox:local .
export SANDBOX_IMAGE_ID="$(docker image inspect soj-sandbox:local --format '{{.Id}}')"
docker image inspect "$SANDBOX_IMAGE_ID"
```

表示IDを`.env`へ保存し、[変更の反映](#変更を反映する)の手順でrunnerを再作成してください。

### TLSファイルのmountに失敗する

`.env`のパスとファイル権限を確認します。

```sh
ls -l deploy/tls/fullchain.pem deploy/tls/privkey.pem
./deploy/rootless-compose.sh config --quiet
```

### Docker統合テストだけ失敗する

rootless判定とcgroup controllerを再確認してください。

Unix socket接続が制限される環境では、rootless Dockerがホストで動作していても
Docker統合テストを実行できないことがあります。
Permission denied等でsocketに接続できない場合は、実行環境のアクセス制限を確認し、未実施の統合検査として報告します。
rootful接続やsandbox制限の緩和で回避しないでください。
