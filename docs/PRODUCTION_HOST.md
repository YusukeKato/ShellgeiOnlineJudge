# 本番ホストの初期設定

ホストを新設・変更する作業者向けの手順です。設定後は[デプロイ手順](./PRODUCTION.md)へ進みます。
`soj`と`/home/soj`は専用ユーザーとホームの例です。実環境に置き換えてください。

## 専用ホストとrootless Docker

- 他用途と共有しないVMと非特権OSユーザーを用意する。
- 専用ユーザーを`docker`・`wheel`・`sudo`グループへ追加しない。
- 専用ユーザーのホームに不要なSSH鍵・クラウド資格情報を置かない。
- 同じDocker daemonで他サービスの重要なコンテナを動かさない。
- runnerは1 instanceで運用する。replicaを増やすと実行上限も増える。
- VM・DBのバックアップを別ホストへ保管する。

共通の導入手順は[前提環境](./DEVELOPMENT.md#1-前提環境)と
[rootless Dockerの設定](./DEVELOPMENT.md#2-rootless-dockerの設定)に従ってください。
Composeのbuild・起動だけなら、ホストへのPoetry導入は不要です。

専用ユーザーで、接続先と資源制限を確認します。

```sh
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
docker info --format '{{json .SecurityOptions}}'
docker info --format 'CgroupDriver={{.CgroupDriver}} CgroupVersion={{.CgroupVersion}}'
cat "/sys/fs/cgroup/user.slice/user-$(id -u).slice/user@$(id -u).service/cgroup.controllers"
```

[cgroupの判定基準](./DEVELOPMENT.md#cgroupによる制限の確認)を満たすことを確認してください。
制限を検証できない場合、runnerは起動を拒否します。
rootless Dockerも完全な隔離境界ではありません。[セキュリティモデル](../SECURITY.md)を確認してください。

## Amazon Linux 2023の設定例

この節は**管理者ユーザー**で実行します。Docker CEのpackage repositoryは構成済みとします。

```sh
cat /etc/os-release
stat -fc %T /sys/fs/cgroup
```

`stat`が`cgroup2fs`であることを確認してから、必要なpackageを導入します。

```sh
sudo dnf install -y docker-ce-rootless-extras
command -v dockerd-rootless-setuptool.sh
command -v newuidmap
command -v newgidmap
```

専用ユーザーが未作成の場合だけ作成します。

```sh
sudo useradd --create-home --shell /bin/bash soj
id soj
sudo grep '^soj:' /etc/subuid /etc/subgid
```

subordinate UID・GIDをそれぞれ65,536個以上割り当ててください。
自動割当がない場合は、管理者が既存範囲と重複しない値を設定します。

`/etc/systemd/system/user@.service.d/delegate.conf`を管理者が次の内容で作成します。

```ini
[Service]
Delegate=cpu cpuset io memory pids
```

設定を反映し、ログアウト後もuser serviceを維持します。
既にuser managerが起動している場合の反映方法は[共通手順](./DEVELOPMENT.md#cgroupによる制限の確認)も確認してください。

```sh
sudo systemctl daemon-reload
sudo loginctl enable-linger soj
SOJ_UID="$(id -u soj)"
SOJ_RUNTIME_DIR="/run/user/${SOJ_UID}"
sudo systemctl start "user@${SOJ_UID}.service"

sudo -iu soj env \
  XDG_RUNTIME_DIR="${SOJ_RUNTIME_DIR}" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=${SOJ_RUNTIME_DIR}/bus" \
  dockerd-rootless-setuptool.sh install

sudo -iu soj env \
  XDG_RUNTIME_DIR="${SOJ_RUNTIME_DIR}" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=${SOJ_RUNTIME_DIR}/bus" \
  systemctl --user enable --now docker
```

以降は専用ユーザーへログインし、[接続先と資源制限の確認](#専用ホストとrootless-docker)を実施します。
rootfulから移行する場合の停止・撤去は[移行後の確認](#再起動と移行後の確認)に従ってください。

## 公開経路とTLS

推奨する経路は次のとおりです。

```text
Internet :443 → ホスト側proxy → https://127.0.0.1:8443 → frontend → backend
```

`.env`は`HTTPS_BIND_ADDRESS=127.0.0.1`、`HTTPS_PORT=8443`とし、公開443番を
ホスト側proxyで受けます。ロードバランサーを前段に置く場合も、この内部経路へ接続してください。
frontendもTLSを要求するため、upstreamにはHTTPSを使用します。

外側proxy・WAFには次を設定してください。これらはComposeの管理外です。

- 公開hostのallowlist、正しいHost header、upstream TLS検証。
- request body上限、client単位とhost全体のリクエスト頻度・burst・接続数制限。
- 提出API（`/api/shellgei`、`/api/v3/submissions`）とその他のpathを分けた制限。
- frontend nginxより長いupstream timeout。body・timeoutの基準は[HTTPの制約](../SECURITY.md#ネットワークとhttpの制約)を参照。
- 必要な場合だけWebSocketのupgrade header。

単一hostでの外側nginxの初期値は次のとおりです。容量とtrafficに合わせて調整します。

| 対象 | clientごと | host全体 |
| --- | --- | --- |
| 通常request | 平均20件/秒、burst 40 | 平均100件/秒、burst 200 |
| 提出API | 平均1件/秒、burst 3 | 平均10件/秒、burst 10 |
| 同時接続 | 20 | 200 |
| 提出APIの処理中接続 | 3 | 上記のhost全体の上限内 |

rate・connection limitの拒否statusは429とします。
複数host・frontend replicaでは、load balancerやWAFによる共有の受付制御を用意してください。
Compose内nginxには実client単位の制限がありません。

受信した`X-Forwarded-For`を無条件に信頼せず、確認できる接続元からclientを判別します。
client IPは揮発性の受付制御にだけ使い、access/error logやWAF eventへ保存しません。
監視はclient識別子・header・query・bodyを含まない413・429・5xxの集計値にしてください。

firewallを次のように設定します。

| ポート | 公開条件 |
| --- | --- |
| 443 | 公開HTTPS |
| 80 | 選択した証明書更新方式で必要な場合だけ |
| 22 | 管理元IPに限定 |
| 8443・PostgreSQL | インターネットへ公開しない。DBはhost port自体を設けない |

SELinux Enforcingで標準nginx policyを使う場合は、upstream接続を確認し、必要な場合だけ管理者が設定します。

```sh
getsebool httpd_can_network_connect
sudo setsebool -P httpd_can_network_connect 1
```

rootless Dockerから直接443を公開する構成は、外側に同等の受付制御がある場合に限ります。
[Docker公式手順](https://docs.docker.com/engine/security/rootless/tips/#exposing-privileged-ports)で
追加権限の影響を確認してから、`.env`を`HTTPS_BIND_ADDRESS=0.0.0.0`、`HTTPS_PORT=443`へ変更してください。

## 証明書の配置と更新

専用ユーザーで証明書の配置先を作成します。

```sh
install -d -m 700 /home/soj/certificates
```

管理者側の証明書取得・更新処理で、次の順序を守ってください。

1. 更新した`fullchain.pem`と`privkey.pem`を保護された一時ファイルへcopyする。
2. 両方をparseでき、公開鍵が一致することを確認する。
3. 上記ディレクトリの**既存ファイルへcopy**する。renameで置き換えない。
4. 所有者を専用ユーザーにし、証明書を`644`、秘密鍵を`600`にする。
5. host側とfrontend側で`nginx -t`を実行する。
6. 両方の検査が成功した場合だけ、frontend、host側の順にreloadする。

単一ファイルのbind mountは、renameで置き換えると古い証明書を参照し続ける場合があります。
秘密鍵をコマンド出力・Gitへ含めないでください。
`.env`の`TLS_CERTIFICATE_PATH`・`TLS_PRIVATE_KEY_PATH`に配置先の絶対pathを設定します。

frontendの検査とreloadは、専用ユーザーでリポジトリrootから実行します。

```sh
./deploy/rootless-compose.sh exec -T frontend nginx -t &&
  ./deploy/rootless-compose.sh exec -T frontend nginx -s reload
```

証明書更新schedulerを設定してください。

- Certbotのdeploy hookは`/etc/letsencrypt/renewal-hooks/deploy/`にroot所有・mode `755`で配置する。
- `certbot renew`はcronまたはsystemd timerの一方だけで実行する。
- standalone方式は更新時に80番を使う。proxyが80番を使う場合はwebroot等へ変更するか、安全な停止・再開手順を用意する。
- `certbot renew --dry-run`に`--run-deploy-hooks`を付けない。本番証明書の上書きを避ける。
- 証明書の有効期限、更新hookの成功、schedulerの稼働を監視する。

proxy・firewall・証明書更新設定は、秘密鍵や`.env`と分離し、アクセス制御された構成管理へ保存してください。

## 再起動と移行後の確認

公開経路で次を確認してください。

- body上限超過は413、client単位のburst超過は429になる。
- client識別情報を含まない413・429・5xxの集計値を取得できる。
- `docker inspect soj-db --format '{{json .HostConfig.PortBindings}}'`が空または`{}`である。
- 8443番が外部interfaceでlistenしておらず、外側proxyが受信した`X-Forwarded-For`を無条件に信頼しない。

初回デプロイ後はOSを再起動し、次を確認してください。

- proxyと証明書更新schedulerが自動起動する。
- `loginctl show-user soj -p Linger`が`Linger=yes`になる。
- 専用ユーザーの`systemctl --user status docker`でrootless daemonが稼働している。
- Composeの4サービスが起動し、runnerがhealthyになる。
- 公開URLからAPIとcommand実行を確認できる。確認方法は[デプロイ手順](./PRODUCTION.md)を参照。

rootfulから移行した場合は、rootless環境の動作を確認した後、管理者がsystem側だけを停止・maskします。

```sh
sudo systemctl disable --now docker.service docker.socket containerd.service
sudo systemctl mask docker.service docker.socket containerd.service
```

OS再起動後もsystem側が停止したままで、user側rootlessが自動復旧することを確認してください。
Docker関連packageは削除しません。rootlessも同じ`dockerd`・`containerd`のbinaryを使用します。

旧データの撤去は、この再起動確認後に行います。削除前に管理者が次を確認してください。

- rootless側の`docker info --format '{{.DockerRootDir}}'`で現在の保存先を確認する。
- system側のdocker・socket・containerdがinactiveかつmaskedで、root権限の関連processが残っていない。
- 旧保存先（通常`/var/lib/docker`・`/var/lib/containerd`）配下にmountが残っていない。
- 旧保存先に必要なDB・volume・imageがなく、バックアップを確保している。
- 専用ユーザーのrootless保存先（通常`~/.local/share/docker`）を削除対象へ含めていない。

対象を確認してから旧rootfulデータと旧配置の`.env`・証明書copyを撤去してください。
