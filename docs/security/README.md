# セキュリティ課題と対応状況

## 目的

この文書は、現在のセキュリティ課題、対応状況、優先順位を追跡する正本です。
後日、開発者や新しいCodexセッションが実装を再開するときの入口として使用します。

この文書は、security modelやsandbox仕様そのものの正本ではありません。
現在の仕様は[SECURITY.md](../../SECURITY.md)、
本番構成と運用手順は[本番運用](../PRODUCTION.md)を参照してください。
今回の監査で確認した根拠と検証結果は、
[2026-08-23監査記録](./audit-2026-08-23.md)に保存しています。

この文書より、現在のコード、設定、テスト、実環境を優先します。
再開時は各課題が現在も成立するか、必ず再検証してください。

## Current baseline

- 最終確認日: 2026-08-24
- branch: `main`
- 確認対象commit: `0d49505e0b9df2978255031e178ecc77dba30140`
- commit subject: `fix: cache problem catalog at startup`
- 今回の変更開始時のworktree: clean
- 対象: repository、rootless Docker開発環境、保存済みimage
- 対象外: 本番host、外側reverse proxy、WAF、実際の本番DBと監視基盤

baseline以降に変更がある場合は、先に差分を確認してください。

```sh
git status --short
git log -1 --oneline
git diff 0d49505e0b9df2978255031e178ecc77dba30140..HEAD
```

## Current security status

- Criticalとして確定した未解決課題はありません。
- Highとして確定したOpen課題はありません。
- repository内のHigh blocking issueは解決しています。
- インターネット公開には、外側proxyまたはWAFの
  実client単位の受付制御を別途確認する必要があります。
- runner異常終了後のsandboxは再起動時に回収します。
  Docker daemon単独の有効期限はないため、SOJ-002を部分解決として追跡します。
- read-only root、tmpfs容量・inode、CPU、memory、swap、PID、
  capability、network、IPC、timeout等の主要sandbox制限は実装され、
  現在のrootless開発環境で実効値を確認しています。
- backendからDocker socketを外し、認証付き内部runnerへ分離した設計は有効です。
  ただし、runnerと他serviceは同じrootless daemonとVMを共有しています。
- 本番の外側proxy、kernel、LSM、filesystem quota、監視、backup等は
  repositoryだけでは確認できません。

## Issue tracker

Statusは次の意味で使用します。

- `Resolved`: 現在のコードとテストで合理的に解決を確認
- `Open`: 未解決で、実装または追加検証が必要
- `Partially resolved`: 一部の経路は塞いだが残存経路がある
- `Deferred`: 意図的に後回しとし、理由を記録済み
- `Cannot verify`: repositoryと現在の環境だけでは判断不能

### Open / Partially resolved / Deferred

- `SOJ-002` — Medium / P1 / Partially resolved
  - 概要: 起動時回収とDocker失敗時の追跡は実装したが、
    daemon単独のsandbox有効期限はない
  - 関連: `backend/scripts/container_manager.py`、`backend/runner_main.py`
  - 次: runner再起動・回収失敗の監視と、独立した期限強制の要否を判断
- `SOJ-005` — Medium / P1 / Open
  - 概要: sandbox、base、DB imageが可変tagで、
    検証済みartifactを保証しない
  - 関連: `docker-compose.yml`、各`Dockerfile`
  - 次: digest固定、artifact promotion、SBOM・署名・scanを導入
- `SOJ-006` — Medium / P1 / Deferred
  - 概要: runner侵害時の影響が同一daemon上のDB、frontend、TLS鍵へ及ぶ
  - 関連: `docker-compose.yml`
  - 次: runner専用hostまたは使い捨てVMへ分離
- `SOJ-007` — Medium / P1 / Open
  - 概要: backendのrunner HTTP clientがproxy環境変数を継承し得る
  - 関連: `backend/scripts/runner_client.py`
  - 次: proxyを明示的に無効化し、内部通信testを追加
- `SOJ-008` — Medium / P1 / Open
  - 概要: NUL出力とDB stallで500またはevent loop停止が起き得る
  - 関連: `backend/api/api_shellgei.py`、`backend/scripts/database.py`
  - 次: 保存用正規化、timeout、rollback、同期DB処理分離を実装
- `SOJ-009` — Medium / P2 / Open
  - 概要: 文字列置換と画像先頭除外により判定衝突が起きる
  - 関連: `backend/scripts/judge.py`
  - 次: 比較方法を修正し、全問題回帰を実行
- `SOJ-010` — Medium / P1 / Open
  - 概要: trailing slash redirectがHTTP schemeと任意Hostを反映し得る
  - 関連: `backend/main.py`、`frontend/nginx/default.conf`
  - 次: redirect無効化、Host・proxy trustを明示
- `SOJ-011` — Medium / P2 / Deferred
  - 概要: backend containerとDB runtime roleの権限が大きい
  - 関連: `backend/Dockerfile`、`docker-compose.yml`
  - 次: non-root最小imageとDB owner/app role分離を設計
- `SOJ-012` — Medium / P2 / Partially resolved
  - 概要: DB行数・Docker service logは制限したが、host I/O、
    DB volume、image cacheにquotaがない
  - 関連: `docker-compose.yml`、`backend/scripts/execution_log_retention.py`
  - 次: 専用filesystem、I/O制御、quota、監視を本番設計へ追加
- `SOJ-013` — Medium / P2 / Open
  - 概要: backend、runner、Docker、DBを通る実Compose E2Eと
    version一致検証がない
  - 関連: `docker-compose.yml`、`backend/tests/test_runner_boundary.py`
  - 次: protocol/data digest確認とrootless E2Eを追加
- `SOJ-014` — Medium / P2 / Open
  - 概要: 対応範囲のPython 3.14でtimeout/concurrency testが失敗する
  - 関連: `backend/scripts/run_shellgei.py`、`pyproject.toml`
  - 次: 実装とruntime差を切り分け、CI matrixかPython上限を決定
- `SOJ-015` — Medium / P1 / Open
  - 概要: cgroup検査とmount前提が、可変sandbox image内の
    tool・metadataを信頼する
  - 関連: `backend/scripts/container_manager.py`、`docker-compose.yml`
  - 次: image digest固定、予期しないmount拒否、volume cleanupを追加
- `SOJ-016` — Medium / P2 / Deferred
  - 概要: 第三者JavaScriptとCSP不足により、
    command/result DOMの影響範囲が広い
  - 関連: `frontend/public/index.html`、`frontend/nginx/default.conf`
  - 次: analytics方針とCSPをbrowser E2E込みで設計
- `SOJ-017` — Low / P2 / Open
  - 概要: frontend nginx設定がhostからread-write mountされる
  - 関連: `docker-compose.yml`
  - 次: mount削除またはread-only化しCompose testを追加
- `SOJ-018` — Low / P2 / Open
  - 概要: runnerが認証前にbodyを読み、healthがpool劣化を検知しない
  - 関連: `backend/runner_main.py`
  - 次: pre-parse auth/body上限とreadinessを追加
- `SOJ-019` — Medium / P2 / Deferred
  - 概要: CIにdependency/image/secret scan、最小token権限、
    artifact保証がない
  - 関連: `.github/workflows/`
  - 次: CI権限固定と継続scanを段階導入
- `SOJ-020` — Low / P3 / Deferred
  - 概要: DBをloopback公開し、Compose外では弱いfallback URLがある
  - 関連: `docker-compose.yml`、`backend/scripts/database.py`
  - 次: 本番port非公開化と設定fail-closedを検討
- `SOJ-021` — Low / P3 / Deferred
  - 概要: command/output保持と非公開脆弱性報告手順を改善できる
  - 関連: `backend/models/model_db.py`、`SECURITY.md`
  - 次: データ最小化方針と報告窓口を決定

現在の未解決trackerは次の内訳です。

- Open: 10件
- Partially resolved: 2件
- Deferred: 6件
- Severity: High 0件、Medium 14件、Low 4件

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
| RES-014 | nginxの共有実行開始枠を廃止し、検証後のrunnerを開始頻度の正本に限定 | この変更 | nginx静的test、実nginx integration test |

RES-003、RES-007、RES-008、RES-009、RES-011、RES-012、RES-013、
RES-014は、
記載した範囲では解決済みです。
daemon単独のsandbox有効期限、可変image等の残存経路は、
別のtracker issueとして追跡しています。

## Open issue details

### SOJ-002: runner crash後の独立した期限強制

問題:

- watchdogはrunner process内のthreadであり、runner停止中は期限を強制できません。
- Docker daemonだけでsandboxを期限切れにする機能は実装していません。
- runnerが再起動しない場合、sandboxは起動時回収まで残る可能性があります。

重要性:

- Composeの`restart: always`と起動時回収が正常に働けば、残存時間は限定されます。
- daemon障害やrunner再起動失敗が重なる場合は、回収が遅延します。

現在の防御:

- owner・runner instance labelと一意なcontainer名
- 同じownerの旧sandboxをpool作成前に削除し、失敗時はrunner起動を拒否
- containerをcreate直後から管理し、start前の失敗も名前から回収
- 回収確認不能なcontainer名をprocess内hard capへ保持
- cleanupの直列化と、実行thread終了後の最終削除
- Composeの`restart: always`

不足と次の対応:

- productionでrunner再起動、起動時回収、owner別container数を監視する
- 1 ownerにつきrunnerを1 instanceに限定する
- runnerとは独立したhost監視またはreaperが必要か運用要件を決定する
- 独立したreaperを追加する場合は、Docker socket権限の増加と分離方法を先に評価する

想定変更範囲:

- production監視・alert設定
- 必要と判断した場合のみ、runnerと独立した回収component

残存リスクを踏まえ、SOJ-002はMedium、P1、Partially resolvedとします。

## Deferred issues

### Architecture変更が必要

- SOJ-006は、runnerを専用hostまたは使い捨てVMへ移す必要があります。
  現在の内部HTTPは平文・固定URLであり、そのまま別hostへ公開してはいけません。
- SOJ-011は、runtime image、migration、DB roleを同時に整理する必要があります。
  小さなsecurity patchとは別phaseにします。

### Product・browser方針が必要

- SOJ-016は、Google Analytics、Google Fonts、CSPの要件決定が必要です。
- SOJ-021は、実行ログの利用目的、保持期間、backup、脆弱性報告窓口の
  運用判断が必要です。

### CI・運用基盤が必要

- SOJ-019は、CI token権限、dependency/image scan、SBOM、署名、
  artifact promotionを段階的に導入する必要があります。
- SOJ-020は、本番のDB管理方法を決めてからport公開を分離します。

Deferredは不要という意味ではありません。
必要な前提が整った時点でseverityとpriorityを再評価してください。

## Production-only verification

### 外側reverse proxy、TLS、client IP

- Repository guarantees:
  - Compose frontendは既定で`127.0.0.1:8443`だけに公開します。
  - 内部nginxはTLS 1.2/1.3、body・connection・proxy timeoutを設定します。
- Development environment verified:
  - repositoryのnginx設定testとlocal smoke testがあります。
  - rootless Docker上の実nginxで、共有実行開始枠がないことを確認しています。
- Production verification required:
  - 公開443のTLS設定、証明書更新、HSTS、Host allowlist
  - upstream証明書検証、実client単位rate/connection limit、XFF trust

### rootless Docker、kernel、runtime isolation

- Repository guarantees:
  - wrapperとrunnerがrootful、TCP Docker、cgroup不備をfail-closedで拒否します。
- Development environment verified:
  - Docker 29.7.2、rootless、cgroup v2、systemd driver
  - builtin seccomp有効、capability 0、`no-new-privileges=1`、swap 0
- Production verification required:
  - Docker、containerd、runc、kernelのversionとsecurity update
  - cgroup delegation、builtin seccomp、AppArmor/SELinuxの実状態
  - rootless userのsubuid/subgidと、専用VM・専用userの維持

### storage、logging、monitoring、backup

- Repository guarantees:
  - DB execution logとCompose service logには上限があります。
  - 現在の制限値は`SECURITY.md`を正本とします。
- Development environment verified:
  - retention unit・PostgreSQL integration testを実行しました。
  - 動的sandboxのlogging driver `none`とPID 1のstdio分離を検証しました。
- Production verification required:
  - VM、Docker data、DB volumeの容量・inode quotaとalert
  - PostgreSQL WAL、autovacuum、backup、restore test
  - orphan sandbox、Docker error、429、5xx、timeoutの監視

### secretsと権限

- Repository guarantees:
  - `.env`、TLS key、Git履歴はDocker build contextから除外します。
  - runner secretはbackendとrunnerだけへ渡します。
- Development environment verified:
  - tracked fileと99 commitsの簡易pattern scanで高確度secret候補は0件でした。
- Production verification required:
  - secret生成・rotation・保管、`.env` mode、backup暗号化
  - GitHub token権限、branch protection、secret scanning、push protection
  - TLS private keyをrunner daemonの影響範囲から分離できるか

## Test coverage

### 現在存在する重要test

- `backend/tests/test_input_validation.py`
  - problem ID、path traversal、command長、NUL、extra JSON field
- `backend/tests/test_container_manager.py`
  - hard cap、rootless/cgroup fail-closed、create/start失敗、
    起動時回収、cleanup競合
- `backend/tests/test_run_shellgei.py`
  - timeout、出力上限、実行slot、background cleanup
- `backend/tests/test_runner_boundary.py`
  - secret、固定schema、response上限、backend/runner分離
- `backend/tests/test_nginx_config.py`
  - nginx directiveの静的確認
- `backend/tests/integration/test_nginx_admission.py`
  - 実nginxで、非実行requestと正常requestが
    共有のsandbox開始枠を消費しないこと
- `backend/tests/integration/test_docker_executor.py`
  - 実containerの起動時回収、filesystem、resource、logging、
    isolation、timeout、画像、状態分離
- `backend/tests/integration/test_postgres_retention.py`
  - 実PostgreSQLの期間・件数制限
- `backend/tests/integration/test_full_problem_regression.py`
  - 現在の92問の正解commandとjudge互換性

実行条件とコマンドは、
[Docker統合テスト](../../backend/tests/integration/README.md)を参照してください。

### 不足しているtest

- 実runner processの強制終了とCompose自動再起動を含むE2E
- Docker create応答timeoutとdaemon停止を使うfailure test
- 実Composeのfrontend -> backend -> runner -> Docker -> DB E2E
- 実nginxのHost、redirect、security header
- DB停止、lock、timeout、commit失敗、NUL、rollback後の回復
- judge collision、画像全byte比較
- backend/runnerのrevision・problem manifest不一致
- dependency、container image、secret、workflowの継続scan
- 外側proxyと複数送信元を含む負荷・公平性test

fork bomb、host disk枯渇、daemon停止等は、通常の開発PCで実行しません。
必要な場合は、watchdogとsnapshot復元を備えた使い捨てVMを使用してください。

## Recommended next steps

再開時は、現在のコードでseverityと成立条件を再確認したうえで進めます。

```text
Next
  SOJ-007 / SOJ-008 / SOJ-010: runner通信・DB・redirectを修正
    ↓
Later
  judge、artifact、権限分離、E2E、browser、CI、運用基盤を改善
```

Highとして確定したOpen課題はありません。
以降はMedium以下を1項目ずつ、または密接に関連する
小さな単位で差分をレビューして進めてください。

## 作業再開手順

1. 現在の`main`、HEAD、worktreeを確認する。
2. baseline commitからの差分を確認する。
3. OpenとDeferredの各項目が現在も成立するか、コードと設定で再検証する。
4. Critical、High、P0からseverityとpriorityを再評価する。
5. 1項目、または密接に関連する小さな修正単位を決める。
6. 修正前に攻撃経路、互換性、失敗時動作、必要testを確認する。
7. production codeと同時にunit、integration、関連文書を更新する。
8. 実行可能な静的検査、unit、Docker integration、回帰testを実行する。
9. 人間が差分とtest結果をレビューしてからcommitする。
10. このtrackerのStatus、関連commit、test情報、baselineを更新する。

文書とコードが食い違う場合は、文書を根拠に実装を続けず、
現在のコード、設定、test、環境を再調査してください。

## Codex再開用プロンプト

```text
現在のmainとHEAD、worktreeを確認し、
docs/security/README.mdのセキュリティ課題を参照してください。
ただし文書を鵜呑みにせず、現在のコードと設定でOpen項目がまだ成立するか
再検証してください。最も優先度の高い未解決項目を特定し、
攻撃経路、互換性、修正範囲、必要なtestを実装前に確認してください。
その後、レビュー可能な小さく安全な単位で実装・test・関連文書更新を行い、
差分と結果を提示してください。明示的な承認なしにcommitやpushはしないでください。
```
