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

> 次の防御は構成されていません。
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
          -> runner API（認証付き内部network）
            -> rootless Docker socket
              -> sandbox containers（networkなし、リソース制限あり）
      -> PostgreSQL（127.0.0.1:5432）
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

現在のCompose構成では、Web APIとDocker操作を固定schemaの内部runner APIで
分離しています。影響範囲をさらに限定するには、runnerとsandbox用daemonを
専用hostまたは使い捨てVMへ配置します。
詳細は[セキュリティモデルと制約](../SECURITY.md)を参照してください。

## 2. OSとrootless Dockerの準備

必要なソフトウェアとrootless Dockerの導入手順は、
開発環境の[「1. 前提環境」](./DEVELOPMENT.md#1-前提環境)と
[「2. rootless Dockerの設定」](./DEVELOPMENT.md#2-rootless-dockerの設定)を正本とします。

本番では、専用の非特権OSユーザーでrootless daemonを起動し、
次の値を本番反映前に確認します。

```sh
docker info --format '{{json .SecurityOptions}}'
docker info --format 'CgroupDriver={{.CgroupDriver}} CgroupVersion={{.CgroupVersion}}'
cat "/sys/fs/cgroup/user.slice/user-$(id -u).slice/user@$(id -u).service/cgroup.controllers"
```

次の条件が必要です。

- Dockerがcgroup v2を使用している
- cgroup driverがsystemdである
- controller一覧に`cpu`、`memory`、`pids`が含まれる

controllerが不足する場合は、
[開発環境のcgroupによる制限の確認](./DEVELOPMENT.md#cgroupによる制限の確認)に従い、
systemd側でcontrollerをdelegateしてから本番運用を開始してください。

runnerは起動時にdaemonのcgroup構成と、各sandboxに反映されたCPU、
メモリ、PID数の上限を検査します。
検査に失敗したsandboxは破棄され、初期poolを作成できない場合は
runnerが起動しません。

## 3. アプリケーションの配置

デプロイユーザーでリポジトリを配置します。

```sh
git clone https://github.com/YusukeKato/ShellgeiOnlineJudge.git
cd ShellgeiOnlineJudge
poetry install
```

運用では、検証済みのrelease tagまたはcommitを明示的に選んでください。未検証のブランチ先端を自動的に本番反映しないでください。

## 4. 本番用の環境変数

環境変数の一覧と既定値は[`.env.example`](../.env.example)を正本とします。
サンプルをコピーし、本番固有の値を上書きします。

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
RUNNER_SHARED_SECRET=runner認証用の64文字のランダム16進数

HTTPS_BIND_ADDRESS=127.0.0.1
HTTPS_PORT=8443
TLS_CERTIFICATE_PATH=/home/soj/certificates/fullchain.pem
TLS_PRIVATE_KEY_PATH=/home/soj/certificates/privkey.pem

SERVER_URL=https://example.com
REACT_APP_SOJ_URL=https://example.com
```

注意点は次のとおりです。

- `POSTGRES_PASSWORD`と`DATABASE_URL`内のパスワードを一致させる
- URLの予約文字を含むパスワードは`DATABASE_URL`側でpercent-encodingする
- `.env`をGitへ追加しない
- `RUNNER_SHARED_SECRET`にはDBパスワードとは異なる値を使用する
- `REACT_APP_*`はfrontendのJavaScriptへ埋め込まれる公開値なので、秘密情報を設定しない
- `DOCKER_SOCKET_PATH`はrunnerへmountするデプロイユーザー自身のrootless socketを指定する
- `SERVER_URL`はCORSの許可originなので、公開URLのschemeとhostを正確に指定し、末尾に`/`を付けない
- 実行ログの保持値を変更する場合は、どちらも1以上の整数にする

retention値を小さくした場合、backendの起動時に新しい上限を超えるログを削除します。
削除したログはDBバックアップなしでは復元できません。
既定の保持期間と最大件数は、
[SECURITY.mdの「実行ログとDockerログ」](../SECURITY.md#実行ログとdockerログ)を参照してください。

## 5. TLS証明書と公開ポート

### 推奨: ホスト側で443を終端する

Composeは、既定で`127.0.0.1:8443`だけに公開します。

公開443番は、次のいずれかで終端します。

- クラウドのロードバランサー
- ホスト側reverse proxy

終端後は`https://127.0.0.1:8443`へ転送します。
Compose内のfrontend nginxが適用する現在の制限値は、
[SECURITY.mdの「ネットワークとHTTPの制約」](../SECURITY.md#ネットワークとhttpの制約)を
正本とします。

ホスト側reverse proxy経由では、frontend nginxから見た接続元がproxyに集約されます。
実際のclient単位で、外側の層にも次を設定してください。

- frontend nginxの上限以下のrequest body
- 接続数とリクエスト頻度
- burst
- upstream timeoutはfrontend nginxの現在値より長くする
- 429、413、5xxの記録と監視

外側proxyは、受信した`X-Forwarded-For`を無条件に引き継がず、
直接接続元から確認したclient IPを基に制限してください。
frontend nginxも受信した`X-Forwarded-For`を破棄し、
自身への直接接続元だけをbackendへ渡します。

Compose内のfrontendもTLSを要求します。
内部転送先はHTTPではなくHTTPSです。

Layer 7 proxyには次を設定します。

- 適切なHost header
- upstream TLS検証
- WebSocketを使用する場合のupgrade header

単純なTCP pass-throughを使う方法もあります。

### 代替: rootless Dockerから443を直接公開する

rootlesskitへ非特権ポート未満をbindする権限を与える方法は、
権限追加の影響を確認したうえで使用してください。

[Docker公式rootless modeのTips](https://docs.docker.com/engine/security/rootless/tips/#exposing-privileged-ports)を参照し、
設定後に`.env`を次のように変更します。

```dotenv
HTTPS_BIND_ADDRESS=0.0.0.0
HTTPS_PORT=443
```

いずれの構成でも、firewallでは必要な公開ポートだけを許可してください。PostgreSQLの5432番と内部用8443番をインターネットへ公開しないでください。

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

## 6. 本番反映前の検証

本番と同じrootless構成のstagingまたは専用CI runnerで実行します。

- Pythonとfrontendの検査は、[開発環境の「6. テスト」](./DEVELOPMENT.md#6-テスト)を実行する
- Docker統合テストと全問題の回帰テストは、
  [Docker統合テスト](../backend/tests/integration/README.md)に従って実行する

本番ホスト上でfork bomb、ディスク枯渇、daemon停止、大量コンテナ生成など、極端な負荷条件を扱う耐性試験を実行してはいけません。
これらは使い捨てVMでのみ実施します。

## 7. 初回デプロイ

デプロイユーザーのshellで実行します。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
docker pull theoldmoon0602/shellgeibot
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

## 8. 更新デプロイ

更新前にDBのバックアップを取得し、対象commitを確認します。

```sh
git fetch --tags origin
git status --short
git log -1 --oneline
```

作業ツリーがcleanであることを確認して、検証済みのtagまたはcommitへ更新します。
その後、「6. 本番反映前の検証」を通してから再デプロイします。

```sh
./deploy/rootless-compose.sh config --quiet
./deploy/rootless-compose.sh build --pull
./deploy/rootless-compose.sh up -d --remove-orphans
./deploy/rootless-compose.sh ps
./deploy/rootless-compose.sh logs --tail=100 db runner backend frontend
```

`REACT_APP_*`はbuild時に埋め込まれます。これらを変更した場合はfrontendの再buildが必要です。

## 9. ロールバック

障害時は、DB schemaやデータ形式の互換性を確認したうえで、
直前に検証済みだったtagまたはcommitをcheckoutし、同じbuild・`up -d`手順を実行します。

DBを以前の状態へ戻す場合は、事前に取得したバックアップから復元します。

`docker compose down -v`はロールバック操作ではありません。
名前付きvolumeを削除してDBデータを失うため、本番運用では実行しないでください。

## 10. 日常運用コマンド

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
- backendの5xx、timeout、拒否数、応答時間
- runnerの認証失敗、429、5xx、再起動、sandbox削除失敗
- rootless Docker user serviceの稼働状態
- sandboxコンテナ数と削除失敗
- TLS証明書の有効期限と更新hookの成功
- OS、Docker、Python/npm依存関係、base imageのセキュリティ更新
- 実行ログのretention件数・期間と、Dockerログへの機密情報混入

rootless Dockerのデータは通常、
デプロイユーザーの`~/.local/share/docker`配下にあります。

daemon稼働中のこのディレクトリをそのままコピーしても、
DBバックアップの代わりにはなりません。
PostgreSQLの整合性が保証される方法でバックアップしてください。

## 12. 運用上の制約

- 同時実行数とrunnerの開始頻度はrunnerプロセス単位です。
  frontend nginxの全体開始頻度はfrontend instance単位です。
  workerやreplicaを増やす前に、共有された受付制御が必要です。
- sandboxイメージはtag参照です。更新時は全問題回帰テストを行い、digest固定、署名検証、SBOM、脆弱性スキャンを導入してください。
- Composeだけでは、DDoS、分散リクエスト、ホストディスク枯渇を完全には防げません。外側のロードバランサー、firewall、監視、容量制限も必要です。
- rootless Dockerはcontainer escapeの影響を軽減しますが、任意コマンド実行サービスの完全な隔離境界ではありません。
