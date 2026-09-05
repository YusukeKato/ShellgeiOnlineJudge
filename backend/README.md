# SHELLGEI ONLINE JUDGE: backend

`backend` directoryには、FastAPIによる公開Web API、内部runner API、
問題の判定、実行ログの保存、sandboxコンテナの管理を行うPythonコードがあります。

## 主な構成

- `soj_shared/`: 入力検証、実行・問題model、問題repository、内部protocol、request contextと構造化log
- `soj_backend/`: `main.py`と`api/`による公開API、提出use case、判定、runner HTTP client、DB接続・保存・保持処理
- `soj_backend/models/`: 公開API DTO、提出結果、typed実行ログ、DB model
- `soj_backend/migrations/`: legacy実行ログ表から構造化schemaへ進めるversioned migration
- `soj_runner/`: `main.py`による認証付き内部API、sandbox pool、archive・出力上限・watchdog・終了処理
- `soj_tools/`: 問題schema移行・manifest生成とホスト監視CLI。本番imageへは収録しない
- `tests/`: 単体・API・Docker統合テスト

依存方向は`soj_backend -> soj_shared <- soj_runner`です。共有packageは公開API・DB・
Docker実装や画像判定へ依存せず、backendとrunnerは互いの専用packageをimportしません。
共有logに必要な提出status enumは`soj_shared/submission_status.py`、
両APIで使うcommand入力の検証は`soj_shared/submission_request.py`に配置しています。
public DTO・内部protocolのfieldとschema名は維持しています。

内部Pythonの旧module名への互換shimは設けていません。ComposeとDockerfileの起動先は
`soj_backend.main:app`・`soj_runner.main:app`です。手動の起動・運用scriptも新module名へ揃えてください。
DB管理CLIは`soj_backend.database_admin`、問題整備CLIは
`soj_tools.problem_migration`・`soj_tools.problem_manifest`です。

## 開発とテスト

環境構築、Pythonの静的検査、単体テストは、
[開発環境の構築・テスト・起動](../docs/DEVELOPMENT.md)を参照してください。

実際のsandboxコンテナを使用するテストは、
[Docker統合テスト](./tests/integration/README.md)を参照してください。

problem schema、manifest revision、移行・更新手順は、
[問題データ](../problems/README.md)を参照してください。

ホスト監視CLI `python -m soj_tools.sandbox_health`の使用方法は、
[本番運用の監視手順](../docs/PRODUCTION.md#runnerとは独立したsandbox監視)を参照してください。

## 本番runtime image

`backend/Dockerfile`は`backend`と`runner`の独立した最終targetを持ち、Composeが
serviceごとに選択します。target未指定の場合は`backend`をbuildします。
共有packageと各targetの専用packageをdirectory単位でCOPYします。
moduleの追加時は責務に対応するpackageへ配置し、反対側の実装を共有packageへ持ち込まないでください。
import方向は静的test、本番imageの全module importと収録境界はDocker統合testで検証します。

| 対象 | 収録するもの | 収録しないもの |
| --- | --- | --- |
| 共通 | API framework依存、`soj_shared`、schema v3と画像data | Poetry、pytest、ruff、mypy、型stub、test、開発CLI、legacy問題data・script |
| backend | `soj_backend`、Pillowによる画像判定、runner HTTP client、DB driver・repository・migration | Docker SDK、sandbox実行・管理module、runner endpoint |
| runner | `soj_runner`、内部API、Docker SDK、sandbox実行・管理module | 公開API、画像判定・Pillow、DB driver・repository・migration |

共有の構造化logは提出結果modelへ依存しません。Pillowは判定を行うbackend groupだけに導入します。
Poetryは固定versionでbuild stageにだけ導入し、`poetry.lock`から`main,backend`または
`main,runner`の依存を専用venvへinstallします。
ホストの通常の`poetry install`は開発用groupも導入します。

実行UID、read-only filesystem、socket権限は
[SECURITY.md](../SECURITY.md#backendrunnerの実行権限)、socket GIDの設定方法は
[開発手順](../docs/DEVELOPMENT.md#runner用socket-groupの設定)を正本とします。
本番container内にはPoetryがないため、運用commandは`python -m soj_backend.database_admin`
のように実行します。imageの検証方法は[Docker統合テスト](./tests/integration/README.md#本番runtime-imageの検証)を参照してください。

## 内部runner protocol

backendからrunnerへの実行境界は、`soj_shared/runner_protocol.py`の
`RunnerGateway`、`RunnerExecutionRequest`、`RunnerExecutionResponse`と、
`soj_shared/models/execution.py`の`ExecutionResult`を正本とします。requestとresponseは
`protocol_version: 3`、backend生成の`request_id`、起動時検証済み
problem dataのSHA-256 `problem_revision`を必須とし、
未知version、未知field、欠落field、文字列・画像上限超過を拒否します。

requestは`protocol_version`、`request_id`、`problem_revision`、`shellgei`、
`problem_id`、responseは`protocol_version`、`request_id`、`problem_revision`と
構造化された`result`で構成します。両processのrevisionまたはrequest IDが
異なる場合は実行結果を受理せずfail-closedとします。
`result`は`status`、
分離した`stdout`・`stderr`、`exit_code`、`timed_out`、`truncated`、
`duration_ms`、任意の`artifact`・`error`を保持します。
artifactはproblem schemaと一致する`path`、`media_type`、Base64 `data`を保持します。
これは外部公開APIではなく、backendとrunnerを同時に更新する内部protocolです。
実行endpointはbody parse前にBearer認証し、認証後のbodyも8 KiBまでとします。
`/internal/health`はprocessのliveness、`/internal/ready`はproblem revisionと
sandbox poolのreadinessを返します。認証、body上限、readinessのsecurity上の
保証は[SECURITY.md](../SECURITY.md#runnerとdocker-socketの権限)を参照してください。
legacy submission APIとDBの互換列には結合済み出力・数字判定codeをmappingします。
v3 submission APIとDBの構造化列は分離した実行・判定情報を保持します。
公開field・HTTP status・legacy互換性の正本は[Public API](../docs/API.md)です。

## 提出use case

`SubmitSolutionService`は、検証済みcommandとproblem IDを受け取り、problem存在確認、
runner実行、判定、実行ログ保存の順に処理します。結果は
`soj_backend/models/submission.py`の`SubmissionResult`として返し、HTTP statusや既存response形式への
変換は`soj_backend/api/api_shellgei.py`だけが担当します。

problem未登録、runner混雑、runner停止は判定結果と別のstatusです。runnerが返した
timeoutや出力上限到達は実行・判定結果として保存します。DB保存だけが失敗した場合は、
実行・判定結果を失わず、保存IDなしの結果を返します。judgeの予期しない例外は
wrong answerへ変換しません。

## 実行ログとDB migration

`soj_backend/models/execution_log.py`の`ExecutionLogEntry`は、problem ID、command、構造化された
実行metadataと判定だけをrepositoryへ渡します。IP address、HTTP header、User-Agent、
画像artifact、内部errorはfieldとして受け取らず、`soj_backend/execution_log_repository.py`も
保存しません。利用目的、保持期間、backupを含むsecurity仕様は
[実行ログとDockerログ](../SECURITY.md#実行ログとdockerログ)を正本とします。

backendは起動時にschemaが`head`であることと、PostgreSQLのruntime roleの権限を
読み取りだけで確認します。未migration・未知revision・過剰/不足権限では受付を開始しません。
SQLiteの単体testではschema revisionだけを検査します。権限境界は実PostgreSQLで検証します。

管理処理は`soj_backend.database_admin`を使用します。`MIGRATION_DATABASE_URL`でschemaを
更新し、`head`指定時は`DATABASE_URL`のユーザー・passwordから専用runtime roleを設定します。
接続設定の条件は[共通する環境変数](../docs/DEVELOPMENT.md#共通する環境変数の条件)、
許可する権限は[DB権限境界](../SECURITY.md#dbの管理用資格情報と通常実行role)を参照してください。
CLIは`.env`を自動読込せず、失敗時にURL・SQL・内部例外を出力しません。

ComposeのDBにはhost portを設けません。管理service・コンテナ内clientの使用方法は
[DBへの管理アクセス](../docs/DEVELOPMENT.md#dbへの管理アクセス)を参照してください。
ホスト上で別途用意したDBへ接続する場合は、両URLをホストから到達できる同じDBへ明示し、repository rootで実行します。
管理用schema・専用roleの準備は、backendを停止して行います。

```sh
PYTHONPATH=backend poetry run python -m soj_backend.database_admin head
```

migrationとrole設定はそれぞれtransactionです。migration成功後にrole設定が失敗した場合は、
schemaだけ更新済みとなり得ます。backendを起動せず原因を解消して`head`を再実行してください。
role設定は冪等でpasswordも同期します。既存の特権role・他role所属・所有物があるroleは、
自動降格や所有者変更をせず拒否します。runtime用には新しい専用role名を使ってください。
DBのPUBLIC CREATE/TEMP、public schemaのPUBLIC CREATE、管理対象表・sequenceのPUBLIC権限を
取り消すため、他アプリと共用するDBにはそのまま適用しません。既存roleの列単位grant等が
ポリシーに反する場合も、検査で拒否し、無関係な権限を自動的に整理しません。

明示revisionへのrollbackはschemaだけを戻し、roleを削除しません。
低水準の`database_migrations` CLIはschema単体の検証用に残しますが、本番更新は管理CLIを使用します。
[本番の更新・既存環境移行](../docs/PRODUCTION.md#8-更新デプロイ)と
[ロールバック](../docs/PRODUCTION.md#9-ロールバック)を参照してください。

text判定は`ExecutionResult`から`TextJudgeInput`へ必要項目だけを渡し、
file I/Oを行わないpure functionへ分離しています。判定規則の正本は
[問題データのText判定](../problems/README.md#text判定)を参照してください。

## 参考

下記記事を参考にさせていただきました。

- FastAPI + nginx: https://qiita.com/junzai/items/4b737a4fafbe888bc709
