# 本番デプロイ手順

専用ユーザーのBash・rootless Dockerで操作します。コマンドはリポジトリのルートで実行してください。
**各手順が成功してから次へ進みます。更新に`down`やvolume削除は不要です。**

| 今回の作業 | 実施する順序 |
| --- | --- |
| 初めて構築する | [初回準備](#初回準備) → [作業開始](#作業開始) → [設定](#本番用の設定) → [ビルド](#ビルド) → [反映](#db更新とサービス起動) → [動作確認](#動作確認) |
| 既存サーバを更新する | [作業開始](#作業開始) → [更新デプロイ](#更新デプロイ) |
| main pushで自動更新する | [SSH自動更新の初回設定・障害対応](./AUTODEPLOY.md) |
| エラーが出た | [失敗した場合](#失敗した場合) |
| OS・公開経路・証明書を設定する | [ホスト設定](./PRODUCTION_HOST.md) |
| 製品リリースを準備する | [リリース準備](./RELEASE.md) |

## 初回準備

1. [ホスト設定](./PRODUCTION_HOST.md)で専用VM・専用ユーザー、rootless Docker、cgroup、TLS、外側proxy・firewallを準備する。
2. ホストにGit、curl、Python 3、OpenSSLを用意する。Composeでのbuild・起動にPoetryは不要。
3. 専用ユーザーでリポジトリを取得する。

```sh
git clone https://github.com/YusukeKato/ShellgeiOnlineJudge.git
cd ShellgeiOnlineJudge
```

4. 検証済みのrelease tagまたはcommitを選ぶ。cloneした直後のブランチ先端を未検証で公開しない。

```sh
(
  set -eu
  read -r -p '検証済みのtagまたはcommit: ' SOJ_TARGET_REF
  test -n "$SOJ_TARGET_REF"
  git switch --detach "$SOJ_TARGET_REF"
  git log -1 --oneline
)
```

## 作業開始

自動更新を導入した環境では、先に[自動更新の停止と状態確認](./AUTODEPLOY.md#4-失敗した場合)を行い、
実行中unitがないことを確認してから手動更新します。自動生成の`docker-compose.override.yml`が
あると、そのimage IDが手動buildしたtagより優先されます。手動方式へ戻す場合は、旧overrideを
保存して退避し、`.env`の`SANDBOX_IMAGE_ID`も手動buildのIDへ合わせてください。

専用ユーザーのshellで実行します。`cd`の配置先は実環境に合わせてください。

```sh
cd /home/soj/ShellgeiOnlineJudge || exit 1
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
```

接続先・ソース・稼働状態を確認します。rootlessでなければここで停止します。

```sh
(
  set -eu
  case "$(docker info --format '{{json .SecurityOptions}}')" in
    *name=rootless*) ;;
    *) echo 'rootless Dockerが必要です' >&2; exit 1 ;;
  esac
  git log -1 --oneline
  git status --short
  docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
)
```

未コミット変更がある場合は差分を確認し、保持・レビューしてからGitを更新します。
以降、環境変数は`.env`に保存します。過去にexportした設定値は`.env`より優先されるため、
別の設定をexportしたshellは使わず、専用ユーザーで新しくログインして作業を開始してください。

## 本番用の設定

### .envを用意する

初回だけコピーします。既存の`.env`は上書きせず、必要な項目だけ編集してください。

```sh
(
  set -eu
  test ! -e .env
  test ! -L .env
  cp .env.example .env
  chmod 600 .env
)
```

新規の秘密値は用途ごとに`openssl rand -hex 32`で生成します。
既存DBの管理passwordはそのまま使用してください。

| .envの項目 | 作業者が設定する値 |
| --- | --- |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | DB管理ユーザー・password・DB名。既存DBでは変更しない |
| `MIGRATION_DATABASE_URL` | 上記の管理資格情報で`db:5432`へ接続するURL。DB構造の更新と通常用ユーザーの設定に使用 |
| `DATABASE_URL` | 同じDBへ接続する、別ユーザー・別passwordのURL。backendの通常処理に使用 |
| `DOCKER_SOCKET_PATH` | `printf '%s\n' "${DOCKER_HOST#unix://}"`の出力 |
| `DOCKER_SOCKET_GID` | [次の手順](#socket-gidを調べる)で測定した整数 |
| `SANDBOX_IMAGE_ID` | [sandbox手順](#sandbox専用image)で取得した`sha256:...` |
| `SANDBOX_OWNER_ID` | 環境固有の名前。例：`shellgei-online-judge-production` |
| `RUNNER_SHARED_SECRET` | DB passwordとは別に生成したランダム値 |
| `HTTPS_BIND_ADDRESS` / `HTTPS_PORT` | 外側proxyを使う構成では`127.0.0.1` / `8443` |
| `TLS_CERTIFICATE_PATH` / `TLS_PRIVATE_KEY_PATH` | 専用ユーザーが読める証明書・秘密鍵ファイルの絶対path |
| `SERVER_URL` / `VITE_SOJ_URL` | 実際の公開origin。例：`https://shellgei-online-judge.com`。末尾の`/`は付けない |
| `VITE_UPDATE_DATE` | 画面に表示する更新日 |

DB URLは次の対応になります。passwordの文字列は実際の値に置き換えてください。

```dotenv
MIGRATION_DATABASE_URL=postgresql://soj_user:管理用password@db:5432/soj_db
DATABASE_URL=postgresql://soj_app:通常用の別password@db:5432/soj_db
```

通常用ユーザーは未作成でも構いません。後述の管理処理が作成します。
URLの文字・driver等の条件は[環境変数の正本](./DEVELOPMENT.md#共通する環境変数の条件)、
保持期間・件数と縮小時の削除は[実行ログの保持仕様](../SECURITY.md#実行ログとdockerログ)を参照してください。
`.env`・秘密鍵はGitへ追加しません。`VITE_*`へ秘密情報を設定しません。

### socket GIDを調べる

初回、またはdaemon・UID/GID mapping変更時に実行します。ホストのGIDではなく、
コンテナ内から見た値が必要です。検査用imageのbuildだけでは稼働runnerは更新されません。

```sh
(
  set -eu
  docker build --file backend/Dockerfile --target runner --tag soj-runner:socket-check .
  docker run --rm --network none --user 0:0 --read-only \
    --cap-drop ALL --security-opt no-new-privileges \
    --mount "type=bind,src=${DOCKER_HOST#unix://},dst=/run/docker.sock,readonly" \
    soj-runner:socket-check python -c 'import os; print(os.stat("/run/docker.sock").st_gid)'
)
```

最後に表示された整数を`.env`の`DOCKER_SOCKET_GID`へ保存してください。
`--user 0:0`はこの属性検査だけに使用します。[詳細](./DEVELOPMENT.md#runner用socket-groupの設定)

### sandbox専用image

初回、またはsandboxを更新するときに実行します。通常の更新では検証済みIDを維持できます。

```sh
(
  set -eu
  docker build --file deploy/sandbox/Dockerfile --tag soj-sandbox:local .
  docker image inspect soj-sandbox:local --format '{{.Id}}'
)
```

表示された`sha256:...`を**`.env`の`SANDBOX_IMAGE_ID`へ保存**してください。exportだけでは次回に残りません。
runnerはimmutable IDまたは`name@sha256:...`を要求します。tagだけでは起動できません。
local IDがdaemonに存在しない場合、runnerはpullせず失敗します。

収録内容・ShellGeiDataの最新取得・cacheの扱いは[sandbox README](../deploy/sandbox/README.md)を参照してください。
再buildで内容が変わり得るため、Git commitだけでなく実imageのIDも記録します。
新しい候補は[検証](#image-digestの更新)を通してから本番へ適用し、旧imageは復帰判断が終わるまで保持します。
CIのarchiveを使う場合は[署名とbuild recordを照合](./CI.md#生成物と検証promotion)してloadし、記録済みIDを設定します。

## ビルド

設定を保存したら実行します。**この手順では稼働サービスを停止・更新しません。**

```sh
(
  set -eu
  ./deploy/rootless-compose.sh config --quiet
  ./deploy/rootless-compose.sh --profile maintenance build --pull
)
```

`db`・`migrate`・`runner`・`backend`・`frontend`の5 imageが成功したら次へ進みます。
sandboxはComposeのbuild対象外です。上の専用手順で用意してください。

## DB更新とサービス起動

既存DBを更新前の状態へ復元する必要がある場合は、整合性のあるbackupと旧設定・旧imageの保存を済ませてから実行します。
この手順はサービスを停止するため、更新時はメンテナンス時間を確保してください。

```sh
(
  set -eu
  ./deploy/rootless-compose.sh config --quiet
  ./deploy/rootless-compose.sh stop frontend backend
  ./deploy/rootless-compose.sh up -d --no-build db

  ready=0
  for attempt in $(seq 1 30); do
    if ./deploy/rootless-compose.sh exec -T db sh -c \
      'pg_isready -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; then
      ready=1
      break
    fi
    sleep 2
  done
  if [ "$ready" -ne 1 ]; then
    echo 'DBが接続を受け付けません。ここで停止します。' >&2
    exit 1
  fi

  ./deploy/rootless-compose.sh run --rm --no-deps -T migrate
  ./deploy/rootless-compose.sh up -d --no-build --remove-orphans
  ./deploy/rootless-compose.sh ps -a
)
```

| 確認箇所 | 成功の目安 |
| --- | --- |
| DB接続待ち | `accepting connections` |
| migration（DB構造・通常用権限の更新） | `0002_structured_execution_logs`、終了code 0 |
| サービス起動 | DB・backend・frontendが`Up`、runnerが`healthy` |

失敗時は[診断](#失敗した場合)へ進みます。migrationはschema更新と権限設定が別transactionなので、
失敗してもschemaだけ更新済みの場合があります。旧backendをそのまま再起動しないでください。

## 動作確認

公開URLは起動中backendの`SERVER_URL`から取得します。提出・sandbox実行・DB保存を1回確認します。
起動直後に502や接続失敗が出た場合は、ログで起動完了を確認してから再実行してください。
`Up`だけではbackend・frontendのHTTP受付開始までは確認できません。

```sh
(
  set -eu
  SOJ_PUBLIC_URL="$(./deploy/rootless-compose.sh exec -T backend \
    python -c 'import os; print(os.environ["SERVER_URL"])')"
  test -n "$SOJ_PUBLIC_URL"
  SOJ_SMOKE_RESPONSE="$(mktemp)"
  trap 'rm -f -- "$SOJ_SMOKE_RESPONSE"' EXIT

  curl --fail --show-error --silent --connect-timeout 10 --max-time 60 \
    --output "$SOJ_SMOKE_RESPONSE" \
    --header 'Content-Type: application/json' \
    --data '{"shellgei":"printf smoke-ok","problem_id":"STANDARD-00000001"}' \
    "${SOJ_PUBLIC_URL}/api/v3/submissions"

  python3 - "$SOJ_SMOKE_RESPONSE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    response = json.load(f)
print(json.dumps(response, ensure_ascii=False, indent=2))
assert response["api_version"] == 3
assert response["execution"]["status"] == "completed"
assert response["execution"]["exit_code"] == 0
assert response["execution"]["stdout"] == "smoke-ok"
assert response["persistence"] == "saved"
assert type(response["submission_id"]) is int and response["submission_id"] > 0
print("sandbox and persistence smoke test: ok")
PY
)
```

最後に`... smoke test: ok`が出れば成功です。問題の正解を出すテストではないので、
`wrong_answer / output_mismatch`は正常です。続いてブラウザで問題一覧・提出・画像問題のJPEG表示を確認します。
GIF表示に対応する更新ではbackend・runner・frontendを同じcommitからbuildして再作成してください。
内部protocolの異なる旧runner/backendを混在させないでください。DB schemaの変更はありません。
確認には画面の「コマンドの例」にあるGIF生成を実行し、生成画像がアニメーションすることを確かめます。
表示条件・制限は[API仕様](./API.md)を参照してください。

初回は[公開制御とOS再起動後の確認](./PRODUCTION_HOST.md#再起動と移行後の確認)も実施してください。

## 更新デプロイ

[作業開始](#作業開始)を実施してから、次の順で進めます。

1. 旧commit、稼働image ID、sandbox IDを運用記録に残す。旧imageは保持する。
2. 更新前のデータへの復元が必要なら、[DB backupと旧設定の保存](#db-backupと旧設定の保存)を実施する。host設定も別途保存する。
3. 検証済みの更新対象を取得し、差分を確認する。

```sh
(
  set -eu
  git rev-parse HEAD
  docker inspect soj-db soj-runner soj-backend soj-frontend \
    --format '{{.Name}} Image={{.Image}} Reference={{.Config.Image}}'
  git fetch --tags origin
  read -r -p '検証済みのtagまたはcommit: ' SOJ_TARGET_REF
  SOJ_TARGET_COMMIT="$(git rev-parse --verify "${SOJ_TARGET_REF}^{commit}")"
  git diff --stat HEAD.."$SOJ_TARGET_COMMIT"
  git diff HEAD.."$SOJ_TARGET_COMMIT" -- .env.example docker-compose.yml docs/PRODUCTION.md SECURITY.md
  printf '更新対象commit: %s\n' "$SOJ_TARGET_COMMIT"
)
```

4. 差分と検証結果を確認後、表示したcommitを指定して切り替える。初回と同じく固定commitで運用する。

```sh
(
  set -eu
  read -r -p '確認済みの更新対象commit: ' SOJ_TARGET_COMMIT
  test -n "$SOJ_TARGET_COMMIT"
  git switch --detach "$SOJ_TARGET_COMMIT"
  git log -1 --oneline
)
```

mainで運用を続ける場合は、上の`git switch`を`git merge --ff-only "$SOJ_TARGET_COMMIT"`に置き換えます。
fast-forwardできない場合は停止して差分を確認し、強制checkoutやresetは使用しません。

5. 次の表に従って反映する。

| 変更内容 | 次の作業 |
| --- | --- |
| 文書のみ | Git更新で終了。サービスのbuild・再起動は不要 |
| コード・問題・依存・Dockerfile・Compose・環境変数 | [設定](#本番用の設定)の差分を反映 → [ビルド](#ビルド) → [DB更新と起動](#db更新とサービス起動) → [動作確認](#動作確認) |
| sandbox更新 | 上記に加え[候補imageを検証してIDを保存](#sandbox専用image) |
| host側proxy・firewall・証明書 | [ホスト設定](./PRODUCTION_HOST.md)を別途反映 |

`VITE_*`とfrontend nginx設定はimageへ組み込まれるため再buildが必要です。
Git更新・build・`restart`だけでは、稼働コンテナは新しいimageへ置き換わりません。

### 旧構成から更新する場合

| 旧構成 | 更新前に行うこと |
| --- | --- |
| backendがDB管理ユーザーで動く | 旧URLを`MIGRATION_DATABASE_URL`へ移し、`DATABASE_URL`には新しい通常用ユーザー・別passwordを設定する。既存の`POSTGRES_*`・DB volumeは維持 |
| `DOCKER_SOCKET_GID`がない | [コンテナ内で測定](#socket-gidを調べる)して保存 |
| DBのhost portを利用していた | DB client・backup・監視を[コンテナ内の管理アクセス](./DEVELOPMENT.md#dbへの管理アクセス)へ切り替える |

`.env`の`POSTGRES_*`を変えても、既存DB内のユーザー・passwordは変わりません。
管理処理は既存の特権ユーザーを通常用へ降格しません。またPUBLIC権限も変更するため、他用途と共有するDBへ適用しません。

## 失敗した場合

まず状態を確認します。URL・passwordを含む`.env`や、秘密値入りのCompose設定全体は共有しないでください。

```sh
./deploy/rootless-compose.sh ps -a
./deploy/rootless-compose.sh logs --tail=100 db runner backend frontend
```

| 症状 | 次に確認すること |
| --- | --- |
| `target stage "runner" could not be found` | Gitのcommitと`backend/Dockerfile`を確認。旧ソースにはrunner targetがない |
| `apk ... unable to select packages` | Dockerfileの固定versionと配布元の変更を確認。[image更新](#image-digestの更新)として修正・検証する。失敗したまま起動へ進まない |
| `service "db" is not running` | DBのbuild・起動エラーを解消し、接続待ちが成功してからmigrationを実施 |
| `database maintenance failed` | 両DB URLの同一host・port・DB、別user・別password、既存管理資格情報、通常用roleの権限を確認。schema更新済みの可能性もある |
| `No services to build`だけ表示 | migration成功の証拠ではない。最終revision・終了codeを確認 |
| runnerが`unhealthy` | rootless/cgroup、socketのpath・GID、sandbox IDの存在、pool作成・回収エラーを確認。制限を緩めず原因を解消 |
| `soj_shared`等が見つからない | 古いimageの可能性。現在のソースでbuildした後、migration成功とコンテナ再作成を確認 |
| 公開APIが405 | 実際の公開ドメインへPOSTしているか確認。外側proxyの転送先はHTTPS |
| `execution_failure` / `execution_error` | runner log・healthとsandbox設定を確認。`persistence: saved`だけでは実行成功ではない |

ソースと稼働imageの確認用です。versionラベルだけではbuild内容の一致までは確認できません。

```sh
git log -1 --oneline
docker inspect soj-backend soj-runner \
  --format '{{.Name}} Image={{.Image}} Version={{index .Config.Labels "org.opencontainers.image.version"}}'
```

## ロールバック

1. frontend/backendを停止し、更新前の記録から復帰先を決める。
2. 次の互換性を確認してからDB・設定・imageを戻す。**Gitだけ戻してもDBは戻りません。**
3. 復帰先の設定検査と起動を行い、[動作確認](#動作確認)を再実施する。

復元コマンドは更新前にstagingで確認して運用記録へ残してください。
タグ指定で起動していたimageは、記録した旧IDを元のimage名へ`docker image tag`で戻し、
旧commit・設定と組み合わせて`up -d --no-build`で再作成します。sandboxも旧IDへ戻します。

| 復帰対象 | 必要な対応 |
| --- | --- |
| schema・権限が同じ版 | 保存したcommit・設定・検証済みimageへ戻す。再buildしたimageは同じ内容とは限らない |
| R3-014より前のbackend | 現在の管理imageで下記のlegacy schemaへの変更を実行してからGitを切り替える |
| SOJ-011より前のbackend | 起動時migrationに管理権限が必要。保護した旧設定の管理URLへ戻す。通常用の最小権限保証は失われる |
| SOJ-020より前のCompose | DBのhost port公開が復活しないよう設定を確認 |
| DB内容の復元が必要 | 保護したbackupから復元。空のDB作成やvolume削除で代用しない |

次は**R3-014より前へ戻す場合だけ**実行します。構造化列を削除しますが、legacy列と行は残します。

```sh
(
  set -eu
  ./deploy/rootless-compose.sh stop frontend backend
  ./deploy/rootless-compose.sh run --rm --no-deps -T migrate \
    python -m soj_backend.database_admin 0001_legacy_execution_logs
)
```

失敗した場合はGitの切替へ進まず、backupからの復元を検討します。
旧imageを削除したり、`down -v` / `down --volumes`でDBを消したりしないでください。

## バックアップと監視

以下のバックアップ手順はデータを保持して復旧する運用向けです。データ消失を許容する
自動更新の方針と手順は[自動更新](./AUTODEPLOY.md)を参照してください。

### DB backupと旧設定の保存

既存DBが稼働している状態で実行します。事前に用意した、アクセス制限・暗号化済みの保存領域を指定してください。
このコマンド自体は暗号化しません。更新前のdump・設定・image一覧を新しい専用ディレクトリへ保存します。

```sh
(
  set -eu
  umask 077
  read -r -p 'backup保存領域の絶対path: ' SOJ_BACKUP_ROOT
  case "$SOJ_BACKUP_ROOT" in /*) ;; *) exit 1 ;; esac
  test -d "$SOJ_BACKUP_ROOT"
  SOJ_BACKUP_DIR="$(mktemp -d "${SOJ_BACKUP_ROOT%/}/soj.XXXXXXXX")"
  cp .env "$SOJ_BACKUP_DIR/env"
  git rev-parse HEAD > "$SOJ_BACKUP_DIR/commit.txt"
  docker inspect soj-db soj-runner soj-backend soj-frontend \
    --format '{{.Name}} Image={{.Image}} Reference={{.Config.Image}}' > "$SOJ_BACKUP_DIR/images.txt"
  ./deploy/rootless-compose.sh exec -T db sh -c \
    'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$SOJ_BACKUP_DIR/database.dump"
  test -s "$SOJ_BACKUP_DIR/database.dump"
  printf 'backup保存先: %s\n' "$SOJ_BACKUP_DIR"
)
```

最後の保存先が表示されなければ失敗です。途中のdumpを復元用として扱わないでください。
dump以後の投稿は含まれません。別hostへ保護して転送し、復元訓練でDB role・所有者・権限も確認します。
`pg_dump`だけではrole定義やhost設定は保存されません。

### 日常の確認

| 項目 | 継続して行う作業 |
| --- | --- |
| DB backup | PostgreSQLの整合性を保証する方法で取得し、暗号化・アクセス制限した別hostへ保管。復元訓練も行う |
| 容量 | Docker領域・DB volumeの容量、inode、quota、CPU・memory・PIDを監視 |
| サービス | runner health・再起動・回収失敗、backendの5xx・timeout・保存失敗を監視 |
| 公開経路 | TLS期限・更新処理、proxyの413・429・5xxの匿名集計を監視 |
| 更新 | OS・Docker・依存・imageのsecurity更新とscanを継続 |

稼働中のDocker data directoryのコピーはDB backupになりません。
保持期間・用途・logへ残せる情報は[実行ログとDockerログ](../SECURITY.md#実行ログとdockerログ)を正本とします。
request IDは単一requestの障害調査にだけ使用します。

状態の確認は次を使用します。

```sh
systemctl --user status docker
journalctl --user-unit docker --since today
docker system df
```

runnerの障害原因を解消して再初期化する場合だけ、次を実行します。

```sh
./deploy/rootless-compose.sh restart runner
./deploy/rootless-compose.sh ps -a
```

`healthy`へ戻ることを確認してください。回収失敗やdaemon障害が続く場合、再起動を繰り返しません。
`docker system prune`は自動実行せず、復帰用imageを含む削除対象を確認します。

### runnerとは独立したsandbox監視

専用ユーザーのホスト監視から、rootless接続と[開発用Poetry環境](./DEVELOPMENT.md)を用意して実行します。
`SANDBOX_OWNER_ID`はComposeと同じ値を設定してください。CLIは`.env`を自動読込しません。

```sh
timeout --kill-after=5s 30s env PYTHONPATH=backend \
  poetry run python -m soj_tools.sandbox_health --owner "${SANDBOX_OWNER_ID:?Set the owner used by Compose}"
```

runner名を変えた場合は`--runner-container`も指定します。例として30秒周期で実行し、
一時的な読み取りのずれによる異常は3回連続で通知します。定期実行・通知はホスト側で設定してください。

| 終了code | 意味・対応 |
| --- | --- |
| `0` | runnerがhealthyで、同じinstanceのsandboxが管理上限数だけrunning |
| `1` | runner停止・非healthy、sandboxの過不足・停止・instance混在。連続時は状態と回収失敗を確認 |
| `2` | 設定・rootless・Docker接続・metadataの確認失敗。監視障害として通知 |
| その他の非0（`124`・`137`等） | 検査全体のtimeout・起動失敗。監視障害として通知 |

出力は1行JSONで、固定issues・state/health・再起動数・sandbox数・instance数を返します。
累積再起動数の増分を監視し、container再作成でのリセットを考慮します。
生のcommand・環境変数・container識別子は返しません。toolは読み取り専用で、削除・再起動・
実行中commandの期限強制は行いません。待機poolの作成時刻だけでは期限超過を判定できません。

## imageの更新と検証

### image digestの更新

外部imageのdigest・package pinの正本は各Dockerfileです。通常の`--pull`では固定digestは変わりません。

1. 候補のdigest・package versionを調べ、Dockerfileと影響するfixtureを同じ変更で更新する。
2. stagingまたは専用CIで[基本検査](./DEVELOPMENT.md#6-テスト)、[Docker・全問題・Compose/browser回帰](../backend/tests/integration/README.md)、[SBOM・脆弱性検査](./CI.md)を実行する。
3. 実imageのID・結果をレビューし、commitした対象を本番へ反映する。CIのreportが存在するだけでは合格扱いにしない。

本番や通常の開発PCでfork bomb・ディスク枯渇・daemon停止等の耐性試験は行いません。
残るsecurity課題と公開条件は[security tracker](./security/README.md)・[SECURITY.md](../SECURITY.md)で確認してください。

### PostgreSQL派生image

DBは[`deploy/postgres/Dockerfile`](../deploy/postgres/Dockerfile)から`soj-db:local`をbuildします。
公式entrypoint・PostgreSQLのmajor version・`PGDATA`を継承し、OpenSSL・libuuidを固定versionで更新、
gosuを修正版Goで再buildします。compiler・source・build cacheは実行imageへ含めません。
取得はAlpineの署名、gosu archiveのchecksumと`go.sum`、`-mod=readonly`で検証します。
固定packageが配布元から消えた場合はbuildを停止し、別versionへ自動fallbackしません。

既存のDB資格情報・`db_data` volumeを維持し、[DB更新互換性test](../backend/tests/integration/README.md)を通して反映します。
元の公式imageへ戻して検出済み脆弱性を再導入しないでください。現在の互換性testはPostgreSQL 15内の更新が対象で、
将来のmajor更新・拡張module・schemaの互換性は別途確認が必要です。
