# main pushからの本番自動更新

既存の本番サーバへGitHub ActionsからSSM経由でSSH接続し、CIで検証した5 imageを配備します。
DB migrationとsandbox更新を含み、バックアップ開始から起動確認まで一時停止します。
初回構築は[本番デプロイ手順](./PRODUCTION.md)、CIの検査内容は[CI文書](./CI.md)を参照してください。

## 1. 本番サーバを準備する

本番が手動デプロイ済みで、公開URLの実行・保存テストが成功していることが前提です。
専用のrootless Dockerユーザーで作業します。

1. Git、Python **3.9以上**、OpenSSHのSFTP、user systemd、rootless Docker・Composeを用意する。
   cgroup v2とuser lingerは[ホスト設定](./PRODUCTION_HOST.md)に従う。
   CI imageはLinux amd64用なので、本番も同じarchitectureを使う。
   `systemd-run --user --wait docker version`が専用ユーザーで成功することも確認する。
   Docker CLIを独自pathへ導入している場合は、user systemdからも実行できるようにする。
2. 自動更新機能を含むcommitを本番checkoutにも取得する。作業treeをcleanにし、
   `.env`、TLS、DB資格情報、`SERVER_URL`が有効な状態にする。
   mainでもdetached HEADでも使用できるが、対象mainへfast-forwardできる必要がある。
3. リポジトリ内に更新管理directoryを作る。バックアップ先は**暗号化された保存領域**に用意する。
   下記pathは実環境に置き換える。両directoryは専用ユーザー所有・mode 700にする。

```sh
cd /home/soj/ShellgeiOnlineJudge
mkdir -m 700 .soj-deploy
mkdir -m 700 /your/encrypted/storage/soj-backups
```

4. Actions専用のSSH鍵を管理端末で作り、公開鍵を本番ユーザーの`~/.ssh/authorized_keys`へ登録する。
   鍵の行には`restrict`を付け、PTY・port forwarding・agent forwardingを許可しない。
   この鍵は本番更新とrootless Dockerの操作権限を持つ。通常の管理用鍵と共用しない。
5. EC2に`AmazonSSMManagedInstanceCore`付きIAMロールを割り当て、SSM Agentを起動する。
   AWSコンソールのSession Managerで接続できることを確認する。
   EC2からSSMへのHTTPS通信が必要。Actions用にSSHのinbound許可を追加する必要はない。
   SSHサーバは起動したままにする。Actionsは`AWS-StartSSHSession`でSSH/SCPを通す。
6. ホスト鍵のfingerprintを本番コンソール等で照合し、`known_hosts`の行を用意する。
   hostname欄は接続先の**EC2 instance ID**にする。標準外portでは`[i-...]:port`形式。
   以前のドメイン名の行はそのままでは一致しない。公開鍵部分は同じ本番host鍵を使用する。
   実行時の無検証`ssh-keyscan`は使用しない。

SSMの対話接続で`ssm-user`から`sudo -iu soj`できることとは別に、Actions専用SSH鍵が
`soj`へ直接認証できる必要があります。自動更新では`ssm-user`を使いません。

既存の`docker-compose.override.yml`を独自に使っている環境では、自動更新を開始しないでください。
自動更新はこのfileを専有し、backend・runner・frontend・DB・migrateのimage IDと
runnerの`SANDBOX_IMAGE_ID`を固定します。通常の`./deploy/rootless-compose.sh`もこれを読みます。
`.env`の旧sandbox IDよりoverrideが優先され、`.env`自体は書き換えません。

## 2. GitHubに設定する

Settings → Environmentsに`production`を作り、Deployment branchesを`main`だけに制限します。
毎回の承認なしで更新する場合はrequired reviewersを設定しません。
mainとworkflow変更はbranch protection/rulesetとコードレビューで保護してください。

先にAWS IAMでGitHub OIDC provider（URL `https://token.actions.githubusercontent.com`、
audience `sts.amazonaws.com`）と、Actions専用ロールを作成します。
信頼ポリシーの`sub`は通常のsubject形式なら
`repo:YusukeKato/ShellgeiOnlineJudge:environment:production`へ完全一致で限定します。
immutable subjectへ移行済みの場合は実際のsubject形式に合わせます。
権限は対象EC2と`AWS-StartSSHSession` documentへの`ssm:StartSession`、
自身のsessionへの`ssmmessages:OpenDataChannel`に限定します。
[公式のSSH用ポリシー](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-getting-started-enable-ssh-connections.html)
を基に、account・region・instanceを実環境に限定してください。
AWSアクセスキーをGitHubへ登録する必要はありません。

**production Environment secrets:**

| 名前 | 設定値 |
| --- | --- |
| `DEPLOY_SSH_KEY` | Actions専用のSSH秘密鍵全文。非対話接続用の鍵 |
| `DEPLOY_KNOWN_HOSTS` | 照合済み本番SSH host鍵のknown_hosts行 |

**production Environment variables:**

| 名前 | 設定値 |
| --- | --- |
| `DEPLOY_AWS_ROLE_ARN` | GitHub OIDC用ロールのARN。EC2のIAMロールとは別 |
| `DEPLOY_AWS_REGION` | EC2のリージョン。例 `ap-northeast-1` |
| `DEPLOY_INSTANCE_ID` | 接続先EC2のinstance ID。`i-...` |
| `DEPLOY_PORT` | SSH port。省略時22 |
| `DEPLOY_USER` | rootless Dockerを所有する専用ユーザー |
| `DEPLOY_REPOSITORY` | 本番checkoutの絶対path。例 `/home/soj/ShellgeiOnlineJudge` |
| `DEPLOY_BACKUP_ROOT` | 上で作ったバックアップ先の絶対path |

pathには空白や`..`を含めず、symlinkを経由しない実pathを指定します。
DB URL、`.env`、TLS秘密鍵はGitHubへ登録・転送しません。

**Repository variables:**

- `PRODUCTION_DEPLOY_ENABLED`: 準備完了後に`true`。未設定なら自動更新しない。
- `VITE_X_URL`、`VITE_GITHUB_REPO_URL`、`VITE_GITHUB_AUTHOR_URL`、`VITE_BLOG_URL`、
  `VITE_MIXI2_URL`: 任意の公開リンク。省略時の値はSupply Chain CIのbuild stepを正本とする。

frontendは同一originのAPIへ接続する設定でCI buildします。
表示更新日（`VITE_UPDATE_DATE`）はCIでfrontendをbuildする際の日本時間の日付を
`YYYY-MM-DD`形式で自動設定します。GitHubへの変数登録は不要で、同名のRepository variableが
残っていても使用しません。配備待ちや再試行で日付をまたいだ場合も、検証済みimageのbuild日を表示します。
本番で再buildしないため、**本番`.env`の`VITE_*`変更は自動更新imageには反映されません**。
公開リンクを変える場合はRepository variablesを変更し、その後のmain pushでbuildします。
backendの`SERVER_URL`は本番`.env`に設定した公開HTTPS originを使用します。

## 3. pushして確認する

有効化後は、レビュー済み変更をmainへpushします。通常は追加操作不要です。

1. Python・React・Supply Chainの**同じcommitのmain push run**がすべて成功するまで待つ。
2. 成功したSupply Chain runのarchiveとbuild recordを取得し、署名者・source SHA・main refを検証する。
3. OIDCでAWSの一時資格情報を取得し、SSM経由のSSHで転送し、本番のuser systemd serviceとして更新する。
4. rootless、clean checkout、既存DB volume、image ID・version・architectureを検証する。
   PostgreSQLのmajor versionまたはPGDATA変更は拒否する。
5. checkoutをfast-forwardし、frontend/backendを停止。旧commit・設定・image ID、
   `pg_dump -Fc`、role情報を専用directoryへ保存する。
6. DB imageを更新、接続待ち、migration、残りのserviceを起動する。
7. 公開HTTPS APIで`printf smoke-ok`の実行とDB保存を確認する。

Actionsの`Production deploy`が成功し、本番の`.soj-deploy/current.json`に対象commitとimage IDが
記録されたことを確認します。スモークテストは実行ログを1件以上保存します。
問題の正答ではないため`wrong_answer`でも正常です。

CI失敗・署名不一致では本番へ接続しません。待機中や転送後にmainが進んでいた場合は古い候補を
取り下げます。実行中の更新を新しいpushでキャンセルせず、host側のlockでも同時更新を拒否します。
CI rerunで復旧した場合は、同じ最新mainに対する`Production deploy`のRe-run all jobsで再試行できます。
ただし停止後の障害は、先に下記の手動復旧が必要です。

SSH切断やActions timeoutだけでは、本番側の更新は止まりません。
本番側は最大40分、停止時の猶予は120秒です。Actions側から安易に再試行せず、
本番のunit・成功記録・障害記録を確認してください。

## 4. 失敗した場合

まずRepository variable `PRODUCTION_DEPLOY_ENABLED`を`false`にし、進行中のsystemd unitを確認します。
この変更だけでは既に始まった更新を停止しません。

```sh
systemctl --user list-units 'soj-deploy-*' --all
# 数字はActions run IDとrun attemptへ置き換える。
journalctl --user -u soj-deploy-123456789-1 --no-pager
cat .soj-deploy/FAILED
./deploy/rootless-compose.sh ps -a
```

停止前の失敗ではサービスを停止しません。ただしimageの取り込みやcheckoutのfast-forwardまで
完了している場合があります。停止後の失敗ではfrontend/backendの停止を試み、`FAILED`を残して
後続の自動更新を拒否します。Docker daemon自体の障害時には、実際に受付が停止したかも確認します。
disk障害で記録できない場合も停止を試みますが、記録fileの有無だけでは更新の成否を判定しないでください。

バックアップは`DEPLOY_BACKUP_ROOT/incoming-<run ID>-<attempt>/`にあります。
`database.dump`、`roles.sql`、`.env`、`compose.json`、`image-ids.json`、`previous-commit`と、
存在した場合は旧overrideを保存します。`compose.json`は解決済み設定の調査用であり、
秘密値を含むためActionsログやissueへ貼らないでください。
backup途中の障害では不完全なfileが残るため、fileの存在だけで復元可能と判断しません。

DB schemaとrole変更は途中まで反映され得るため、旧imageへ自動で戻しません。
[本番の障害対応](./PRODUCTION.md#失敗した場合)に従い、DBとroleの状態、旧image ID、
旧checkoutとoverrideを揃えて復旧します。初回自動更新前は旧overrideがないため、
`image-ids.json`も使って復旧対象を確認してください。
復旧と公開経路テストが成功し、実行中unitがないことを確認してから`FAILED`を作業記録へ移し、
自動更新を再度有効化します。記録だけを消してmigrationを繰り返さないでください。

成功した回の転送archiveだけを自動削除します。失敗時のarchive、旧image、DBバックアップは
自動削除しないため、復旧に必要な世代と容量を確認して運用者が保存期間を管理してください。
本番に新旧image、転送archive、DBバックアップを同時に保持できる空き容量が必要です。

## 検証と保証範囲

ローカルでは`pytest backend/tests/test_deployment.py backend/tests/test_ci_policy.py`と
actionlintで配備条件・停止順序・失敗分岐・権限を検査します。
`backend/tests/integration/test_production_deploy.py`は[Compose E2Eの設定](../backend/tests/integration/README.md)で
実DBのbackup・migration・TLS経由の実行/保存と、migration失敗時の受付停止を確認します。
Git取得とarchive loadは省略し、指定された検証用local imageを使います。
実際のGitHub attestation、OIDC・SSM・SSH経路、systemd、バックアップからの復旧は、導入時に検証用サーバで
確認してください。ローカルのprocess代替テストは実サーバでの受入検証を代替しません。

公式資料: [attestationの検証条件](https://cli.github.com/manual/gh_attestation_verify)、
[deployment environment](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)。
