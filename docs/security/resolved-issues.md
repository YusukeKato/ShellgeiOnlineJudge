# 解決済み課題と部分対応の検証記録

この文書はsecurity課題への対応commitと、その当時の検証結果を保持する記録です。
記録中の未実施・未確認の記述も当時の範囲を示します。本番の現在状態を確認したものではありません。
現在の課題と残存リスクは[セキュリティ課題の入口](./README.md)、
現行仕様は[SECURITY.md](../../SECURITY.md)を参照してください。

- [解決済み課題の一覧](#resolved-issues)
- [SOJ-011: DB runtime roleの分離](#soj-011-db-runtime-roleの分離)
- [SOJ-020: DBのhost port廃止](#soj-020-dbのhost-port廃止と接続設定の必須化)
- [SOJ-002: ホスト監視CLIの部分対応](#soj-002-ホスト監視cliの部分対応)

## Resolved issues

重要な解決済み項目だけを記録します。
実装詳細はcommitとtestを正本とします。

| ID | 解決内容 | 関連commit | 主な確認test |
| --- | --- | --- | --- |
| RES-001 | request固有fileをhost共有pathからin-memory archiveへ移行 | `54eb5e7` | `test_execution_archive.py`、Docker状態分離test |
| RES-002 | Composeとrunnerでrootless Dockerをfail-closedに強制 | `1aec1dc` | `test_compose_config.py`、Docker baseline test |
| RES-003 | 管理対象container数、実行thread、worker slotをprocess内で制限 | `8ed4f80` | `test_container_manager.py`、`test_run_shellgei.py` |
| RES-004 | silent timeout、出力上限、background process破棄を実装 | `f9de53e` | run_shellgei unit、Docker timeout test |
| RES-005 | rootless Docker統合test基盤を追加 | `849e041` | `backend/tests/integration/` |
| RES-006 | problem ID、JSON、command長、入力NUL等を検証 | `a30b0d8` | `test_input_validation.py` |
| RES-007 | root filesystemをread-only化し、tmpfs容量・inodeを制限 | `1492f79` | Docker filesystem・inode・capacity test |
| RES-008 | DB実行ログ件数・期間とCompose service logを制限 | `ac42f29` | retention unit・PostgreSQL integration test |
| RES-009 | sandbox開始頻度とcgroup実効値をfail-closedで検証 | `fd02020`、`d0efe75` | admission、container manager、Docker baseline test |
| RES-010 | Docker socketを公開backendから内部runnerへ分離 | `7cab18e` | `test_runner_boundary.py`、Compose静的test |
| RES-011 | 動的sandboxのDockerログを無効化し、待機PID 1のstdioを`/dev/null`へ分離 | `41d31c8` | container manager unit、Docker baseline test |
| RES-012 | owner単位の起動時回収、create/start失敗追跡、shutdown競合防止を実装 | `71dad03` | container manager unit、Docker restart test |
| RES-013 | 問題一覧を起動時に検証・JSON化し、HTTP cacheを追加 | `0d49505` | problem catalog unit、backend startup test |
| RES-014 | nginxの共有実行開始枠を廃止し、検証後のrunnerを開始頻度の正本に限定 | `7c4ef54` | nginx静的test、実nginx integration test |
| RES-015 | backendからprivate runnerへのHTTP通信で環境proxyの継承を明示的に無効化 | `74a1a74` | runner boundary test、基本Python検査 |
| RES-016 | slash自動redirectを無効化し、backendのHostとforwarded headerの信頼境界を固定 | `6061ebc` | ASGI boundary test、nginx静的test、基本Python検査 |
| RES-017 | 実行ログ保存をevent loop外へ分離し、NUL正規化、DB timeout、rollbackと失敗後の回復を実装 | `3843e37` | persistence unit、PostgreSQL lock failure/recovery integration test |
| RES-018 | Python 3.12--3.14のruntime matrixを固定し、thread future完了確認をversion間で一貫させた | `9510c1f` | runtime matrix、timeout/concurrency、3.12--3.14 non-Docker test |
| RES-019 | text token衝突と画像先頭除外を解消し、schema指定artifactのMIME検証と全画素比較へ分離 | `91fdbad`、`7947640` | text/image judge unit、全問題Docker回帰 |
| RES-020 | runner実行認証をbody読込前へ移し、8 KiB上限、pool readiness、problem revision相互検証を追加 | `07545a5` | runner security・boundary・container manager・Compose静的test |
| RES-021 | server生成request IDとallowlist型JSON eventでbackend・runner・DB保存を紐付け、利用者dataの非記録を検証 | `45d5482` | structured logging・public API・runner・DB boundary test |
| RES-022 | 第三者analytics・外部fontを削除し、frontendのscript・通信を同一originへ制限するCSPを追加 | `872bacf` | frontend unit/build、nginx静的test・HTTPS smoke |
| RES-023 | sandbox・base・DB imageをSHA-256 digestで固定し、tag移動による未検証artifactへの差替えを防止 | `eff33ca` | runtime image pin静的test、image build、Docker統合test |
| RES-024 | sandbox imageの`VOLUME`宣言と作成後の予期しないmountを拒否し、削除時に匿名volumeも回収 | `eff33ca` | container manager unit、Docker baseline test |
| RES-025 | frontend nginx設定をimageへ組み込み、hostからのwritable bind mountを削除 | `eff33ca` | Compose静的test、frontend image build |
| RES-026 | SOJ-013: revision拒否と実行・判定・保存を実Composeで検証し、DB/runner停止復帰・browser E2Eを追加 | `48a0670` | Compose E2E、隔離設定・cleanup test |
| RES-027 | SOJ-011: DB管理serviceと最小権限app roleを分離し、backendはschema・権限を読み取り検証 | `4eec07b` | 実PostgreSQLの禁止操作・旧行保持・rollback、Compose全問題・保存回帰 |
| RES-028 | SOJ-020: DBのhost portを廃止し、backendの明示DB URLと安全な設定診断を必須化 | `17e8ee7` | DB設定process test、Compose port静的test・実port非公開・全問題/保存E2E |

RES-003、RES-007、RES-008、RES-009、RES-011、RES-012、RES-013、
RES-014、RES-015、RES-016、RES-017、RES-018、RES-019、RES-020、RES-021、RES-022、
RES-023、RES-024、RES-025、RES-026、RES-027、RES-028は、
記載した範囲では解決済みです。
daemon単独のsandbox有効期限等の残存経路は、
別のtracker issueとして追跡しています。

### SOJ-011: DB runtime roleの分離

Status: Resolved（依頼者のreview承認後に`4eec07b`でcommit済み）。

2026-09-05、repository上の権限分離を実装・検証しました。本番DBの変更は実施していません。

- backendは起動時にDDLを実行せず、head revisionと通常roleの権限を読み取り検証する。
- maintenance profileの`migrate`だけへ管理URLを渡し、同じbackend imageを一時実行する。
- 既存のDB/表の所有者・行を維持し、別の専用roleで保存・retentionを実行する。
  既存特権role・所有者・他role所属は自動降格せず拒否する。
- 権限の正本は[SECURITY.md](../../SECURITY.md#dbの管理用資格情報と通常実行role)、
  設定・transactionの扱いは[backend文書](../../backend/README.md#実行ログとdb-migration)、
  初回移行・password更新・旧backendへ戻す制約は[本番運用](../PRODUCTION.md#更新デプロイ)を参照する。
- 起動時処理の既存testを変更し、実装前に2件のREDを確認した。
  実PostgreSQLで保存・retention成功、DDL・migration表更新・setval・role昇格の拒否、
  列単位やPUBLICへの追加権限の拒否、旧行・所有者保持とrollback/re-upgradeを検証した。
- Python 3.14でruff・format・mypy・非Docker629件が成功。公開OpenAPIは変更前snapshotと一致。
  Compose設定、文書link、secret scanも成功。最終CLIの修正後にbackend imageを再buildし、
  管理処理・通常role保存を含むruntime4件も再実行して成功した。
- rootless Docker23件が成功。通常roleでの実Compose全92問・browser・DB停止復帰、
  直接sandbox全92問、runtime境界、DB image互換性と監視CLIを含む。
- frontend・依存・image base・sandboxは変更していないため、frontend基本5検査と脆弱性scanは再実行していない。
  GitHub CI・本番移行は未実施。SOJ-006の同一daemon上の影響範囲は別課題として維持する。
  SOJ-020のDB公開は後続の下記対応で解決した。

### SOJ-020: DBのhost port廃止と接続設定の必須化

Status: `Resolved`（2026-09-05、依頼者のreview承認後に`17e8ee7`でcommit済み）。
SOJ-011で内部network上の管理serviceが整ったため、DB管理手段を理由とする延期を解除しました。

- ComposeのDB port公開を廃止し、backendの既定DB URLを削除しました。
  未設定・空・空白だけなら起動を拒否し、URL解析・driver初期化の失敗も資格情報を含まない固定診断へ変換します。
- E2E設定がDB portを消して隠す処理を廃止し、追加を拒否するtestと実containerのport非公開検査を追加しました。
  pytest収集時だけmemory DBを明示し、ホストの資格情報を検証用接続へ引き継ぎません。
- URL未指定と公開portを含む新しい期待値でREDを確認後、対象37件がGREEN。
  Python 3.14のruff・format・mypy、非Docker639件が成功しました。
- 更新したbackend imageでrootless Docker23件が成功（skipなし）。Compose config、実browser、
  直接sandboxとComposeの全92問、DB管理・保存・権限・停止復帰・cleanupを含みます。
- frontendのコード・依存・imageは変更せず、検証済みimageをE2Eで使用しました。frontend基本5検査は再実行していません。
  GitHub CI、本番反映、脆弱性scanは未実施です。

設定と管理手順は[DBへの管理アクセス](../DEVELOPMENT.md#dbへの管理アクセス)、
本番で既存client・backup・監視を切り替える手順は[更新デプロイ](../PRODUCTION.md#更新デプロイ)を参照してください。
DB schema・保存内容・APIは維持します。host portの廃止は、rootless daemonやhostの管理者からのDB隔離を保証しません。

## SOJ-002: ホスト監視CLIの部分対応

今回の実装（2026-09-05、依頼者のreview承認後に`b422b01`でcommit済み）:

- `soj_tools.sandbox_health`を追加。CLIの契約は[本番監視手順](../PRODUCTION.md#runnerとは独立したsandbox監視)を正本とする。
- 識別label・owner検証・pool上限を`soj_runner.sandbox_identity`へ移し、
  監視がruntime managerの初期化や環境変数の副作用を伴わず同じ定義を使えるようにした。値は変更していない。
- 新規testは実装前のmodule未存在によるREDを確認後、31件成功。
  ruff・format・mypy、Python 3.14の非Docker608件が成功。
- runner imageを再buildし、rootless Docker11件が成功。runtime境界・非root・実行/画像判定・DB保存と、
  実sandboxの隔離・出力・timeout・回収を確認。専用の軽量containerでは正常・別owner除外・
  runner停止/削除・停止sandboxと監視の非変更を確認した。
- frontend・依存・問題データ・Composeは変更していないため、frontend基本5検査とCompose/全92問回帰は再実行していない。
  imageのbase・依存とsandbox digestも維持し、脆弱性scanは再実行していない。
- 本番の定期実行・通知設定、独立reaperの導入は未実施。Docker daemon停止等の耐性試験は行っていない。
