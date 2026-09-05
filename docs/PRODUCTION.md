# 本番環境の構築・デプロイ・運用

この文書は、Docker Compose構成をrootless Dockerで本番運用するための手順です。
本番固有の構成、デプロイ、更新、ロールバック、監視手順は、
この文書を正本とします。

ShellgeiOnlineJudgeは、インターネットから任意のシェルコマンドを受け付けます。
一般的なWebアプリより、実行基盤とデータへ及ぶ影響範囲が広いサービスです。

本番環境には次の構成を使用してください。

- 他用途と共有しない専用VM
- 専用の非特権OSユーザー
- rootless Docker

> リポジトリ内のComposeには、次の防御は構成されていません。
>
> - 複数frontend replicaや複数hostで共有する受付制御
> - 外側proxyでの実際のclient単位のリクエスト・接続制限
>
> この文書は起動・運用方法を示すもので、
> 安全なインターネット公開を保証するものではありません。
> [セキュリティモデルと制約](../SECURITY.md)を確認し、
> 外側のロードバランサーやWAFを含む構成全体で公開可否を判断してください。

## 1. 推奨構成

```text
Internet
  -> Firewall / Load Balancer / Reverse Proxy（TLS、接続数制限）
    -> 127.0.0.1:8443
      -> frontend（nginx）
        -> backend（FastAPI）
          |-> runner API（認証付き内部network）
          |   -> rootless Docker socket
          |     -> sandbox containers（networkなし、リソース制限あり）
          `-> PostgreSQL（内部接続はdb:5432、host公開は127.0.0.1:5432のみ）
```

backendにはDocker socketをmountしません。
外部へportを公開しないrunnerだけがrootless Docker socketを使用します。
このsocketからホストrootを直接取得する構成ではありません。

runnerの実行権限が意図しない形で利用された場合、
次のリソースが影響範囲に含まれます。

- rootless daemonが管理する全コンテナ
- Dockerイメージ
- Docker volume
- daemonユーザーがアクセスできるファイル

そのため、次の運用条件を守ってください。

- 専用VMに配置し、他サービスとDocker daemonを共有しない
- 専用ユーザーを`docker`グループや`sudo`グループへ追加しない
- 専用ユーザーのホームに、デプロイに不要なSSH鍵やクラウド資格情報を置かない
- DB、runner、backend、frontend以外の重要なコンテナを同じdaemonで動かさない
- VMやDBを別の信頼境界としてバックアップする

現在のCompose構成では、Web APIとDocker操作をversion付き固定schemaの
内部runner APIで分離しています。protocolの正本は
[backend文書](../backend/README.md#内部runner-protocol)を参照してください。
Compose healthcheckはrunnerのreadinessを使用し、sandbox poolの削除・補充失敗と
problem dataのrevisionを状態に反映します。readinessが劣化した場合は、
runner logとrootless daemonを確認し、原因を解消してからrunnerを再起動します。
影響範囲をさらに限定するには、runnerとsandbox用daemonを
専用hostまたは使い捨てVMへ配置します。
詳細は[セキュリティモデルと制約](../SECURITY.md)を参照してください。

## 2. OSとrootless Dockerの準備

必要なソフトウェアとrootless Dockerの導入手順は、
開発環境の[「1. 前提環境」](./DEVELOPMENT.md#1-前提環境)と
[「2. rootless Dockerの設定」](./DEVELOPMENT.md#2-rootless-dockerの設定)を正本とします。

本番では、専用の非特権OSユーザーでrootless daemonを起動します。
本番反映前の確認コマンドは次のとおりです。

```sh
docker info --format '{{json .SecurityOptions}}'
docker info --format 'CgroupDriver={{.CgroupDriver}} CgroupVersion={{.CgroupVersion}}'
cat "/sys/fs/cgroup/user.slice/user-$(id -u).slice/user@$(id -u).service/cgroup.controllers"
```

出力の判定基準とcontrollerが不足する場合の設定は、
[開発環境のcgroupによる制限の確認](./DEVELOPMENT.md#cgroupによる制限の確認)を
参照してください。

runnerは起動時にdaemonのcgroup構成と、各sandboxに反映されたCPU、
メモリ、PID数の上限を検査します。
検査に失敗したsandboxは破棄され、初期poolを作成できない場合は
runnerが起動しません。

### Amazon Linux 2023での構成例

Amazon Linux 2023では、cgroup v2を使用していることを最初に確認します。

```sh
cat /etc/os-release
stat -fc %T /sys/fs/cgroup
```

`stat`の結果は`cgroup2fs`である必要があります。
Docker CEのpackage repositoryを構成済みの場合、rootless用の追加packageは
次の名前で導入できます。

```sh
sudo dnf install -y docker-ce-rootless-extras
command -v dockerd-rootless-setuptool.sh
command -v newuidmap
command -v newgidmap
```

サービス専用ユーザーを作成します。
以下では例として`soj`を使用します。

```sh
sudo useradd --create-home --shell /bin/bash soj
id soj
sudo grep '^soj:' /etc/subuid /etc/subgid
```

専用ユーザーには、少なくとも65,536個のsubordinate UIDとGIDが必要です。
自動で割り当てられなかった場合は、既存範囲と重複しない値を管理者が
割り当ててください。

専用ユーザーを`docker`、`wheel`、`sudo`などの管理用groupへ追加しないでください。

rootless Dockerからresource controllerを利用できるよう、
`/etc/systemd/system/user@.service.d/delegate.conf`を次の内容で作成します。

```ini
[Service]
Delegate=cpu cpuset io memory pids
```

設定を反映し、ログインしていない状態でもuser serviceを起動できるようにします。

```sh
sudo systemctl daemon-reload
sudo loginctl enable-linger soj

SOJ_UID="$(id -u soj)"
sudo systemctl start "user@${SOJ_UID}.service"
```

rootless daemonのsetupと確認は、実効ユーザーを明示して行います。

```sh
SOJ_UID="$(id -u soj)"
SOJ_RUNTIME_DIR="/run/user/${SOJ_UID}"

sudo -iu soj env \
  XDG_RUNTIME_DIR="${SOJ_RUNTIME_DIR}" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=${SOJ_RUNTIME_DIR}/bus" \
  dockerd-rootless-setuptool.sh install

sudo -iu soj env \
  XDG_RUNTIME_DIR="${SOJ_RUNTIME_DIR}" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=${SOJ_RUNTIME_DIR}/bus" \
  systemctl --user enable --now docker
```

```sh
SOJ_DOCKER_HOST="unix://${SOJ_RUNTIME_DIR}/docker.sock"

sudo -iu soj env \
  XDG_RUNTIME_DIR="${SOJ_RUNTIME_DIR}" \
  DOCKER_HOST="${SOJ_DOCKER_HOST}" \
  docker info --format '{{json .SecurityOptions}}'

sudo -iu soj env \
  XDG_RUNTIME_DIR="${SOJ_RUNTIME_DIR}" \
  DOCKER_HOST="${SOJ_DOCKER_HOST}" \
  docker info \
    --format 'Driver={{.CgroupDriver}} Version={{.CgroupVersion}} Storage={{.Driver}}'
```

`SecurityOptions`に`name=rootless`があり、cgroup driverが`systemd`、
cgroup versionが`2`であることを確認します。

同じホストにrootful daemonが残っている場合は、移行完了後にsystem側だけを
停止・maskします。user scopeのrootless `docker.service`には影響しません。

```sh
sudo systemctl disable --now docker.service docker.socket containerd.service
sudo systemctl mask docker.service docker.socket containerd.service
```

rootless daemonはsystem packageの`dockerd`と`containerd`のbinaryを使用します。
system serviceを停止しても、Docker関連package自体は削除しないでください。

## 3. アプリケーションの配置

デプロイユーザーでリポジトリを配置します。

```sh
git clone https://github.com/YusukeKato/ShellgeiOnlineJudge.git
cd ShellgeiOnlineJudge
```

Composeでbuild・起動するだけなら、ホストへのPoetry導入は不要です。
ホスト上でPythonの静的検査や単体テストを実行する場合に限り、
開発文書に従ってPoetryと依存関係を導入します。
Pythonの対応範囲とproduction imageの基準versionは、
[開発環境の前提環境](./DEVELOPMENT.md#1-前提環境)を参照してください。

運用では、検証済みのrelease tagまたはcommitを明示的に選んでください。未検証のブランチ先端を自動的に本番反映しないでください。

## 4. 本番用の環境変数

本番用の設定も[`.env.example`](../.env.example)を起点とし、
次のようにサンプルをコピーして本番固有の値を上書きします。

```sh
cp .env.example .env
chmod 600 .env
id -u
printf '%s\n' "${XDG_RUNTIME_DIR}/docker.sock"
openssl rand -hex 32  # DB password用
openssl rand -hex 32  # runner認証用
```

用途ごとに異なるランダム値を使い、`.env`を編集します。
以下は本番で上書きが必要な値の例です。
`example.com`、UID、パスワード、証明書のパスは実環境に合わせてください。

```dotenv
POSTGRES_PASSWORD=十分に長いランダム値
DATABASE_URL=postgresql://soj_user:十分に長いランダム値@db:5432/soj_db

DOCKER_SOCKET_PATH=/run/user/1000/docker.sock
SANDBOX_OWNER_ID=shellgei-online-judge-production
RUNNER_SHARED_SECRET=runner認証用の64文字のランダム16進数

HTTPS_BIND_ADDRESS=127.0.0.1
HTTPS_PORT=8443
TLS_CERTIFICATE_PATH=/home/soj/certificates/fullchain.pem
TLS_PRIVATE_KEY_PATH=/home/soj/certificates/privkey.pem

SERVER_URL=https://example.com
VITE_SOJ_URL=https://example.com
```

開発・本番に共通する値の整合条件は、
[共通する環境変数の条件](./DEVELOPMENT.md#共通する環境変数の条件)を参照してください。
初回deployと既存構成からの移行時には、
[runner用socket groupの設定](./DEVELOPMENT.md#runner用socket-groupの設定)に従って
`DOCKER_SOCKET_GID`を実測し、`.env`へ追加してください。未設定ではComposeが設定検査を拒否します。
本番固有の注意点は次のとおりです。

- `.env`をGitへ追加しない
- `RUNNER_SHARED_SECRET`にはDBパスワードとは異なる値を使用する
- frontend build変数の公開範囲と同一origin条件は、
  [frontendのbrowser境界](../SECURITY.md#frontendのbrowser境界)に従う
- `DOCKER_SOCKET_PATH`はrunnerへmountするデプロイユーザー自身のrootless socketを指定する
- `SERVER_URL`はCORSの許可originなので、公開URLのschemeとhostを正確に指定し、末尾に`/`を付けない
- 実行ログの保持値を変更する場合は、どちらも1以上の整数にする

retention値を小さくした場合、backendの起動時に新しい上限を超えるログを削除します。
削除したログはDBバックアップなしでは復元できません。
既定値、DB timeout、保存失敗時の挙動は、
[SECURITY.mdの「実行ログとDockerログ」](../SECURITY.md#実行ログとdockerログ)を参照してください。

## 5. TLS証明書と公開ポート

### 推奨: ホスト側で443を終端する

Composeは、既定で`127.0.0.1:8443`だけに公開します。

公開443番は、次のいずれかで終端します。

- クラウドのロードバランサー
- ホスト側reverse proxy

終端後は`https://127.0.0.1:8443`へ転送します。
Compose内のfrontend nginxが適用するbody・timeout制限は、
[SECURITY.mdの「ネットワークとHTTPの制約」](../SECURITY.md#ネットワークとhttpの制約)を
正本とします。

ホスト側reverse proxy経由では、frontend nginxから見た接続元が
proxyに集約されます。
そのためCompose内nginxはIP単位のrate・connection limitを適用しません。
実際のclient単位で、外側の層に次を必ず設定してください。

- request bodyは16 KiB以下
- 接続数とリクエスト頻度
- burst
- 提出API（`/api/shellgei`、`/api/v3/submissions`）とその他のpathを分けた制限
- host全体の同時接続・request上限
- upstream timeoutはfrontend nginxの現在値より長くする
- 429、413、5xxの集計値による監視

外側proxyは、受信した`X-Forwarded-For`を無条件に引き継がず、
直接接続元から確認したclient IPを基に制限してください。
client IPは揮発性の受付制御にだけ使い、access/error logやWAF eventへ保存しません。
監視にはclient識別子、header、query、bodyを含まないstatus別の集計値を使用します。
frontend nginxからbackendへのHost・forwarded headerの扱いは、
[SECURITY.mdの「ネットワークとHTTPの制約」](../SECURITY.md#ネットワークとhttpの制約)を
正本とします。
外側proxyでは公開hostのallowlistを適用し、受信したforwarded headerを
無条件に信頼せず、直接接続元から確認したclient情報を受付制御に使用してください。

Compose内のfrontendもTLSを要求します。
内部転送先はHTTPではなくHTTPSです。

Layer 7 proxyには次を設定します。

- 適切なHost header
- upstream TLS検証
- WebSocketを使用する場合のupgrade header

単一hostの小規模構成では、次の値を外側nginxの初期値として使用できます。
実際のtrafficとhost容量を監視し、必要に応じて調整してください。

- 通常request: clientごとに平均20件/秒、burst 40
- 通常request: host全体で平均100件/秒、burst 200
- 提出API: clientごとに平均1件/秒、burst 3
- 提出API: host全体で平均10件/秒、burst 10
- 同時接続: clientごとに20、host全体で200
- 提出APIの処理中接続: clientごとに3
- rate・connection limitの拒否status: 429

複数host構成では、この値はhost間で共有されません。
load balancerやWAFなど、全hostで共有される受付制御を別途使用してください。

host側reverse proxy、firewall、証明書更新schedulerはComposeの管理外です。
実際に適用している設定を、秘密鍵や`.env`とは分離して、
アクセス制御されたInfrastructure as Codeまたは構成backupで管理してください。

SELinuxをEnforcingにするhostでは、reverse proxyからloopback上のupstreamへ
接続できることを確認します。Red Hat系の標準nginx policyを使用する場合は、
次のbooleanが必要になることがあります。

```sh
getsebool httpd_can_network_connect
sudo setsebool -P httpd_can_network_connect 1
```

単純なTCP pass-throughを使う方法もあります。

### 限定的な代替: rootless Dockerから443を公開する

Compose内nginxは実client単位のrate・connection limitを持ちません。
そのため、外側のload balancer、WAF、または同等の受付制御なしに
この方法でインターネット公開しないでください。

rootlesskitへ非特権ポート未満をbindする権限を与える方法は、
権限追加の影響を確認したうえで使用してください。

[Docker公式rootless modeのTips][rootless-privileged-ports]を参照し、
設定後に`.env`を次のように変更します。

[rootless-privileged-ports]: https://docs.docker.com/engine/security/rootless/tips/#exposing-privileged-ports

```dotenv
HTTPS_BIND_ADDRESS=0.0.0.0
HTTPS_PORT=443
```

いずれの構成でも、firewallでは必要な公開ポートだけを許可してください。

- 443番は公開HTTPSに使用する
- 80番はCertbot standaloneなど、選択した証明書更新方式で必要な場合だけ許可する
- 22番は管理元のIP addressへ限定する
- PostgreSQLの5432番と内部用8443番はインターネットへ公開しない

### 証明書ファイル

rootless daemonは通常`/etc/letsencrypt`を直接参照できません。証明書をデプロイユーザーが読める専用ディレクトリへ安全にコピーします。

```sh
install -d -m 700 /home/soj/certificates
```

証明書の取得・更新を行う管理者側の処理で、次を実施します。

- `fullchain.pem`と`privkey.pem`を専用ディレクトリへコピーする
- 所有者をデプロイユーザーにする
- 秘密鍵のmodeを`600`にする
- 秘密鍵をコマンド出力やGitへ含めない

ユーザー名と配置先は実環境に置き換えてください。

更新後はfrontendを再読み込みします。

```sh
./deploy/rootless-compose.sh exec frontend nginx -t
./deploy/rootless-compose.sh exec frontend nginx -s reload
```

証明書更新hookでは、コピーが完全に終わってからreloadするようにしてください。

Dockerで単一ファイルをbind mountしている場合、host側でrenameしてinodeを
置き換えると、起動中containerが古いinodeを参照し続けることがあります。
更新用ファイルを検証した後、bind mount先の既存ファイルへcopyしてから
frontendをreloadしてください。

更新hookでは、少なくとも次の順序を守ります。

1. 更新された証明書と秘密鍵を一時ファイルへcopyする
2. 両方をparseでき、公開鍵が一致することを確認する
3. `/home/soj/certificates`の既存ファイルへcopyする
4. 証明書を`644`、秘密鍵を`600`、所有者を専用ユーザーにする
5. host側とfrontend側の`nginx -t`を実行する
6. frontend、host側の順にnginxをreloadする

Certbotのdeploy hookを使用する場合は、通常、
`/etc/letsencrypt/renewal-hooks/deploy/`へroot所有・mode `755`で配置します。
cronとsystemd timerの両方から`certbot renew`を実行せず、どちらか一方だけを
有効にしてください。

standalone authenticatorは更新時に80番を使用します。
host側reverse proxyが80番をlistenする構成では、そのまま併用できません。
webrootなどへ変更するか、更新時の安全な停止・再開方法を別途設計してください。

本番証明書を上書きしないため、`certbot renew --dry-run`へ
`--run-deploy-hooks`を付けないでください。

## 6. 本番反映前の検証

本番と同じrootless構成のstagingまたは専用CI runnerで実行します。

- Pythonとfrontendの検査は、[開発環境の「6. テスト」](./DEVELOPMENT.md#6-テスト)を実行する
- Docker統合テストと全問題の回帰テストは、
  [Docker統合テスト](../backend/tests/integration/README.md)に従って実行する
- frontendからDBまでの経路と停止・復帰は、staging側で
  [ComposeとブラウザのE2E](../backend/tests/integration/README.md#composeとブラウザのe2e)を実行する

本番ホスト上でfork bomb、ディスク枯渇、daemon停止、大量コンテナ生成など、極端な負荷条件を扱う耐性試験を実行してはいけません。
これらは使い捨てVMでのみ実施します。

### image digestの更新

外部image referenceの正本は各Dockerfileと
`backend/soj_runner/container_manager.py`です。通常のdeployでは固定済みdigestを
`--pull`しても同じartifactが取得され、tagの移動だけでは内容が変わりません。

imageを更新するときだけ、次の順序で候補を確認します。

1. rootless Dockerへ更新候補のtagをpullする
2. `docker image inspect --format '{{json .RepoDigests}}' IMAGE:TAG`でregistry digestを取得する
3. 該当するDockerfile、Compose、sandbox定数、統合test fixtureを同じ変更で更新する
4. 基本検査、image build、rootless Docker統合test、全問題回帰testを実行する
5. 検証したdigestと結果をreviewし、commit後に本番へ反映する

候補tagをそのまま本番設定へ記載してはいけません。CIのSBOM・脆弱性scanと、
mainの検査成功時に登録するprovenanceの検証方法は[CI文書](./CI.md)を参照してください。
検査失敗時にもreport artifactを保存するため、artifactの存在だけでdeploy対象を判断しません。
第三者imageの供給元署名等の残存対策は[セキュリティ課題tracker](./security/README.md)で追跡します。

### PostgreSQL派生image

ComposeのDBは[`deploy/postgres/Dockerfile`](../deploy/postgres/Dockerfile)からbuildします。
`soj-db:local`はそのローカルimage名です。公式PostgreSQL imageへ戻すと、今回是正した
OpenSSL・gosuの脆弱性が再導入されるため、通常の起動・更新ではこのbuildを使用してください。
`pull_policy: never`で同名imageのregistry取得を禁止します。起動前に明示的なbuildが必要です。

PostgreSQLのメジャーバージョン、公式entrypoint、`PGDATA`、既存のDB role・credentialを継承し、
OpenSSLだけをAlpineの固定package versionへ更新します。gosuは同じ公式sourceを修正版Goで
再buildし、通常の非root PostgreSQL起動を維持します。Go・PostgreSQLのimage digest、
gosu archiveのSHA-256、OpenSSLのversionはDockerfileを正本とします。
Go compiler・source・build用cacheはDB runtime imageへ収録しません。

gosuはarchiveのchecksumと`go.sum`を検証し、moduleは`-mod=readonly`でbuildします。
Alpine packageはrepository署名と固定versionで取得します。固定packageが配布元から消えた場合は
buildを失敗させ、別versionへ暗黙にfallbackしません。pinの変更はscan・DB互換性testを通してreviewします。

更新時は整合性のあるDB backupを取得し、buildした候補で[DB更新互換性とCompose回帰](../backend/tests/integration/README.md)を
確認してください。DB containerを再作成しても`db_data` volumeは維持します。`down --volumes`や
DB初期化を更新手順に使用しないでください。旧imageへの復帰testはこのPostgreSQL 15内の更新だけを
対象とし、将来のメジャー更新・schema migration・拡張moduleの互換性まで保証しません。

## 7. 初回デプロイ

デプロイユーザーのshellで実行します。

```sh
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
docker pull \
  theoldmoon0602/shellgeibot:latest@sha256:aaaa5b10e6419e4309a0b53a8d9e48ddcadabb92cc1dc7e1a739bc0248741a36
./deploy/rootless-compose.sh config --quiet
./deploy/rootless-compose.sh build --pull
./deploy/rootless-compose.sh up -d --remove-orphans
./deploy/rootless-compose.sh ps
./deploy/rootless-compose.sh logs --tail=100 db runner backend frontend
```

起動後、ローカルと公開経路の両方を確認します。

```sh
curl --fail --show-error --silent --insecure https://127.0.0.1:8443/api
curl --fail --show-error --silent https://example.com/api
```

`--insecure`はlocalhost向け内部確認で、証明書名が公開ドメインと一致しない場合に限って使用します。
公開URLの確認では使用しないでください。

`GET /api`はHTTP経路の確認だけです。
runner、sandbox、DB保存まで確認するには、安全なcommandを1回実行します。

```sh
SOJ_SMOKE_RESPONSE="$(mktemp)"

curl --fail --show-error --silent \
  --output "${SOJ_SMOKE_RESPONSE}" \
  --header 'Content-Type: application/json' \
  --data '{"shellgei":"printf smoke-ok","problem_id":"STANDARD-00000001"}' \
  https://example.com/api/v3/submissions

python3 -c '
import json
import sys

with open(sys.argv[1], encoding="utf-8") as response_file:
    response = json.load(response_file)
assert response["api_version"] == 3
assert response["execution"]["status"] == "completed"
assert response["execution"]["stdout"] == "smoke-ok"
assert response["persistence"] == "saved"
assert type(response["submission_id"]) is int and response["submission_id"] > 0
print("sandbox and persistence smoke test: ok")
' "${SOJ_SMOKE_RESPONSE}"

rm -f -- "${SOJ_SMOKE_RESPONSE}"
```

外側proxyを使用する場合は、公開前に次も非破壊的に確認します。

- 16 KiBを超えるrequest bodyが413になる
- client単位のburstを超えるrequestが429になる
- client識別情報を含まない413、429、5xxの集計値を取得できる
- 8443番と5432番が外部interfaceでlistenしていない
- 受信した`X-Forwarded-For`をclient識別へ無条件に使用していない

### OS再起動後の確認

初回デプロイではOSを再起動し、次を確認してください。

- host側reverse proxyと証明書更新schedulerが自動起動する
- `loginctl show-user <専用ユーザー> -p Linger`が`Linger=yes`になる
- rootless `docker.service`がuser scopeで自動起動する
- Composeの4 servicesが再起動し、runnerがhealthyになる
- rootful `docker.service`と`docker.socket`は起動しない
- 公開URLからAPIとcommand実行を利用できる

## 8. 更新デプロイ

更新は専用ユーザーで実行します。
[「10. 日常運用コマンド」](#10-日常運用コマンド)の環境変数と
作業directoryを設定してから、以下を実行してください。

### 更新前の確認

DBデータを保持する場合は、更新前に整合性のあるbackupを取得します。
実行ログを含むbackupの用途、暗号化、アクセス制限、保持期間は、
[SECURITY.mdの「実行ログとDockerログ」](../SECURITY.md#実行ログとdockerログ)に従います。
作業ツリーがcleanであることと、現在のcommitを確認します。

```sh
git status --short
git log -1 --oneline

SOJ_PREVIOUS_COMMIT="$(git rev-parse HEAD)"
printf 'previous commit: %s\n' "${SOJ_PREVIOUS_COMMIT}"
```

`git status --short`に出力がある場合は、内容を確認するまで更新しないでください。
表示したcommit IDは、shell sessionの外側にある運用記録へ残します。

remoteの変更を取得し、取り込むcommitと差分を確認します。

```sh
git fetch --tags origin

SOJ_TARGET_COMMIT="$(git rev-parse origin/main)"
printf 'target commit: %s\n' "${SOJ_TARGET_COMMIT}"

git log --oneline HEAD.."${SOJ_TARGET_COMMIT}"
git diff --stat HEAD.."${SOJ_TARGET_COMMIT}"
git diff --name-status HEAD.."${SOJ_TARGET_COMMIT}"
```

特に、環境変数、Compose、本番手順、セキュリティ上の前提への変更を確認します。

```sh
git diff HEAD.."${SOJ_TARGET_COMMIT}" -- \
  .env.example \
  docker-compose.yml \
  docs/PRODUCTION.md \
  SECURITY.md
```

`.env.example`に必須変数が追加・変更されている場合は、
Git管理外の本番`.env`にも反映します。
host側reverse proxy、firewall、証明書更新処理への指示がある場合は、
Composeとは別に適用計画を作成してください。

### Gitの更新

検証したtarget commitをfast-forwardで取り込みます。
確認後にremoteが更新されても、別のcommitを意図せず取り込まない手順です。

```sh
git merge --ff-only "${SOJ_TARGET_COMMIT}"
git log -1 --oneline
git status --short
```

release tagやcommitを固定して運用する場合は、`origin/main`を自動的に
取り込まず、検証済みの対象を明示してcheckoutしてください。

### 再デプロイ要否の判断

更新前後のファイル一覧を確認します。

```sh
git diff --name-status "${SOJ_PREVIOUS_COMMIT}"..HEAD
```

変更内容ごとの対応は次のとおりです。

| 変更 | 必要な対応 |
| --- | --- |
| Markdownなど文書だけ | Gitの更新だけ。Composeのbuild・再起動は不要 |
| backend、runner、frontend、問題データ | 設定検査、build、`up -d`、動作確認 |
| Dockerfile、Compose、依存関係 | 設定・環境変数を確認し、build、`up -d`、動作確認 |
| `VITE_*` | frontendへbuild時に埋め込まれるため再buildが必要 |
| host側nginx、firewall、証明書運用 | リポジトリ外の設定へ別途反映 |

判断できない場合は、再デプロイが必要な変更として扱います。

### Composeへの反映

「6. 本番反映前の検証」を完了したcommitを使用します。
まず、rootless daemonと本番`.env`を含むCompose設定を検査します。
backend/runner image分離前の構成から更新する場合は、先に上記のsocket GID設定を追加します。
Composeは両serviceの専用targetをbuildし、非root・read-onlyで再作成します。
DB schema・roleの変更はこのimage分離には含まれず、既存volumeを引き続き使用します。

```sh
./deploy/rootless-compose.sh config --quiet
printf 'compose config exit=%s\n' "$?"
```

終了statusが`0`の場合だけ、buildして反映します。

```sh
./deploy/rootless-compose.sh build --pull
./deploy/rootless-compose.sh run --rm --no-deps backend \
  python -m soj_backend.database_migrations head
./deploy/rootless-compose.sh up -d --remove-orphans
./deploy/rootless-compose.sh ps
./deploy/rootless-compose.sh logs --tail=100 db runner backend frontend
```

`frontend/nginx/default.conf`はfrontend imageへ組み込み、hostからmountしません。
この設定を変更した場合はfrontend imageを再buildし、containerを再作成してください。

単一host構成では、containerの再作成中に短時間の応答断が発生する可能性があります。
更新のために`down`を先に実行する必要はありません。
backendもrequest受付前に同じmigrationを確認します。明示migrationが失敗した場合は
`up -d`へ進まず、DBを変更したまま旧backendを再起動しないでください。

### 反映後の確認

次を確認します。

- DB、backend、frontendがrunningになる
- runnerがhealthyになる
- 起動loop、runner認証失敗、problem revision不一致、sandbox作成・削除・補充失敗がない
- 公開URLの`GET /api`が成功する
- ブラウザから問題一覧を取得できる
- 安全なcommandを1回実行できる

HTTPとsandbox実行の確認方法は、
[「7. 初回デプロイ」](#7-初回デプロイ)と同じです。

## 9. ロールバック

障害時は、更新前に記録したcommit IDを使います。
DB schema、データ形式、`.env`の後方互換性を先に確認してください。
R3-014の構造化実行ログschemaから、それ以前のbackendへ戻す場合は、Gitを切り替える前に
frontendとbackendを停止し、現在のbackend imageでlegacy revisionへ戻します。

```sh
./deploy/rootless-compose.sh stop frontend backend
./deploy/rootless-compose.sh run --rm --no-deps backend \
  python -m soj_backend.database_migrations 0001_legacy_execution_logs
```

このrollbackは構造化列だけを削除し、従来の`output`、`judge`を含むlegacy列と行を残します。
migrationに失敗した場合はcommitの切替へ進まず、更新前backupからの復元を検討してください。

main branch自体を書き換えず、直前のcommitをdetached HEADで一時的に展開します。

```sh
git status --short
git switch --detach "${SOJ_PREVIOUS_COMMIT}"

./deploy/rootless-compose.sh config --quiet
./deploy/rootless-compose.sh build
./deploy/rootless-compose.sh up -d --remove-orphans
./deploy/rootless-compose.sh ps
./deploy/rootless-compose.sh logs --tail=100 db runner backend frontend
```

shellを開き直して変数が失われた場合は、記録したcommit IDを
`${SOJ_PREVIOUS_COMMIT}`の代わりに直接指定します。

DBを以前の状態へ戻す場合は、事前に取得したバックアップから復元します。
Git管理外の`.env`とhost側設定も、必要に応じて個別に戻します。

修正版を再び反映する際は、mainへ戻ってからfast-forwardで更新します。

```sh
git switch main
```

その後、「8. 更新デプロイ」の更新前確認から繰り返します。

`docker compose down -v`はロールバック操作ではありません。
名前付きvolumeを削除してDBデータを失うため、本番運用では実行しないでください。

## 10. 日常運用コマンド

管理ユーザーから操作する場合は、まず専用ユーザーのshellへ移動して
rootless socketを明示します。

```sh
sudo -iu soj
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
cd /home/soj/ShellgeiOnlineJudge
```

ユーザー名と配置先は実環境に合わせてください。

```sh
./deploy/rootless-compose.sh ps
./deploy/rootless-compose.sh logs --tail=200 backend
./deploy/rootless-compose.sh logs --tail=200 runner
./deploy/rootless-compose.sh logs -f frontend backend runner
./deploy/rootless-compose.sh restart backend
./deploy/rootless-compose.sh restart runner
./deploy/rootless-compose.sh down
./deploy/rootless-compose.sh up -d
```

runnerはpool劣化を検知すると非readyを維持します。
`restart runner`で起動時回収とpool再初期化が成功し、`ps`でhealthyへ戻ることを
確認してください。削除失敗やdaemon障害が続く状態で再起動を繰り返さないでください。

ComposeのDB、runner、backend、frontendにはDockerログのrotationが設定されています。
現在の上限値は、
[SECURITY.mdの「実行ログとDockerログ」](../SECURITY.md#実行ログとdockerログ)を参照してください。

適用状態は次のコマンドで確認できます。

```sh
docker inspect --format '{{json .HostConfig.LogConfig}}' \
  soj-db soj-runner soj-backend soj-frontend
```

rootless daemon自体を確認します。

```sh
systemctl --user status docker
journalctl --user-unit docker --since today
docker system df
```

`docker system prune`は、必要なイメージやbuild cacheを消す可能性があります。自動実行せず、削除対象を確認してから運用判断してください。

## 11. バックアップ・監視項目

最低限、次を継続的に確認してください。

- PostgreSQLの定期バックアップと、別ホストへの保管
- バックアップからの復元訓練
- VM、Docker領域、DB volumeのディスク使用量とinode使用量
- DB volumeを配置するfilesystemのquotaと容量アラート
- CPU、メモリ、PID、ロードアベレージ
- backendの5xx、timeout、拒否数、応答時間の集計値
- runnerの認証失敗、429、5xx、再起動、sandbox削除失敗の集計値
- responseの`X-Request-ID`でbackend、runner、DB保存のJSON eventを紐付けられること
- rootless Docker user serviceの稼働状態
- owner別のsandboxコンテナ数、起動時回収、削除失敗
- TLS証明書の有効期限と更新hookの成功
- 証明書更新cronまたはsystemd timerの稼働状態とdry-runの定期確認
- 外側proxyの413、429、5xxとrate・connection limitの匿名集計値
- OS、Docker、Python/npm依存関係、base imageのセキュリティ更新
- 実行ログのretention件数・期間と、service logへのclient情報・機密情報混入

request IDは問い合わせ対象の1 requestを追跡するためだけに使用し、
利用者単位の集計やprofilingに使用しないでください。記録fieldと保持方針は
[SECURITY.mdの「実行ログとDockerログ」](../SECURITY.md#実行ログとdockerログ)を正本とします。

rootless Dockerのデータは通常、
デプロイユーザーの`~/.local/share/docker`配下にあります。

daemon稼働中のこのディレクトリをそのままコピーしても、
DBバックアップの代わりにはなりません。
PostgreSQLの整合性が保証される方法でバックアップしてください。

### runnerとは独立したsandbox監視

rootless Dockerを所有するホストユーザーの既存監視から、repository rootで次を実行します。
ホストには[開発環境](./DEVELOPMENT.md)のPoetry環境（Docker SDKを含む）が必要です。
本番container内へtoolや追加のDocker socket mountを導入する必要はありません。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
timeout --kill-after=5s 30s env PYTHONPATH=backend \
  poetry run python -m soj_tools.sandbox_health
```

Composeと同じ`SANDBOX_OWNER_ID`を環境変数または`--owner`で指定してください。
runnerのcontainer名を変更した環境では`--runner-container`も指定します。
CLIは明示したUnix socketのrootless確認後、同じownerのsandbox一覧とrunnerのinspectだけを読み取ります。
runnerのCompose service labelとowner設定が一致しない場合は確認失敗です。

| 終了code | 意味・対応 |
| --- | --- |
| `0` | このsnapshotではrunnerがrunning/healthyで、同一instanceのsandboxが管理上限数だけrunning |
| `1` | runner欠落・停止・非healthy、sandbox数の過不足・停止・instance混在。連続する場合はrunnerの状態と回収失敗を確認 |
| `2` | 設定不正、rootless不一致、Docker接続失敗、metadata欠損等で確認不能。正常として扱わず監視障害として通知 |

外側の`timeout`による`124`・`137`や、Python/Poetry起動失敗等の他の非0終了も監視障害です。
SDKのtimeoutは各HTTP要求に適用され、検査全体の期限は上記のホスト側timeoutで制限します。
30秒周期等で実行し、起動・pool補充・再起動との非atomicな読み取りによる一時的な`1`は、
例えば3回連続した場合に通知します。実際の通知設定・定期実行の導入は本番監視側で行ってください。

stdoutは1行JSONで、`status`・固定`issues`、runnerのstate/health、累積`runner_restarts`、
`sandbox_count`・`sandbox_not_running`・`instance_count`だけを返します。
再起動数は前回値からの増加を監視し、container再作成でリセットされることに注意してください。
container名・ID、instance labelの値、環境変数、command、healthcheckの生出力、内部例外は出力しません。

このtoolは読み取り専用です。runner停止時の残存sandboxを通知できますが、
削除、runner再起動、実行中commandの経過時間確認、独立した有効期限の強制は行いません。
待機poolは長時間残るのが正常なので、containerの作成時刻だけを期限超過と判定しません。
通知後の回収は[runnerの停止・復旧手順](#10-日常運用コマンド)と
[セキュリティ課題](./security/README.md)を参照してください。

## 12. 運用上の制約

- 同時実行数とrunnerの開始頻度はrunnerプロセス単位です。
  runnerのreplicaを増やすと合計上限も増えるため、現在は1 instanceに限定します。
  複数frontendまたは複数hostでは、外側の共有された受付制御が必要です。
- sandboxを含むruntime imageはdigest固定です。更新時は
  [image digestの更新](#image-digestの更新)に従ってください。
- Composeだけでは、DDoS、分散リクエスト、ホストディスク枯渇を完全には防げません。外側のロードバランサー、firewall、監視、容量制限も必要です。
- rootless Dockerはcontainer escapeの影響を軽減しますが、任意コマンド実行サービスの完全な隔離境界ではありません。

## 13. rootful環境から移行した後の撤去

rootful Dockerから移行する場合は、新しいrootless環境が正常に起動し、
公開経路とOS再起動後の自動復旧を確認するまで旧データを削除しないでください。

rootlessとrootfulの標準的な保存先は異なります。

- rootless: 専用ユーザーの`~/.local/share/docker`
- rootful: `/var/lib/docker`と`/var/lib/containerd`

削除前に、次を確認します。

- `docker info`でrootless側の`DockerRootDir`を確認する
- system scopeのdocker、socket、containerdがinactiveかつmaskedである
- root権限のdockerd、containerd、containerd-shimが残っていない
- `/var/lib/docker`と`/var/lib/containerd`配下にmountが残っていない
- 削除対象に必要なDB、volume、imageがない

rootful側の保存先を削除しても、Dockerのsystem packageは削除しないでください。
rootless daemonが同じbinaryを使用します。

旧リポジトリに`.env`、証明書のcopy、その他の秘密情報が残っている場合は、
新環境の動作確認後に旧配置も削除します。
