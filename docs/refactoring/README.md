# ShellgeiOnlineJudge v3.0.0 Refactoring Tracker

## Purpose

この文書は、ShellgeiOnlineJudge v3.0.0リファクタリングの計画、優先順位、
進捗、完了commit、設計判断を追跡する正本です。
各R3 unitの開始、レビュー依頼、承認、commit、計画変更に合わせて更新し、
unitの実装が完了したのにtrackerだけが古い状態を残さないでください。

この文書は、現在の実装仕様やsecurity modelの正本ではありません。
現在の仕様はrepository内のコードと設定、
[SECURITY.md](../../SECURITY.md)、[セキュリティ課題tracker](../security/README.md)、
[開発手順](../DEVELOPMENT.md)、[本番運用](../PRODUCTION.md)を参照してください。
実装開始時にはbaseline以降の差分と、関連文書の最新状態を再確認してください。

## Status summary

- Target version: `3.0.0`
- Baseline: `2.8.0`
- Baseline commit: `991ef334f2785cce81a2e33206ec1f00f3487c9b`
- Baseline commit subject: `docs: update maintenance history`
- Baseline date: 2026-08-25
- Overall status: `Implementation`
- Total refactoring units: 29
- Ready: 0
- Planned: 3
- Pending (`Ready` + `Planned`): 3
- In Progress: 0
- Review: 0
- Completed: 26
- Blocked: 0
- Deferred: 0
- Superseded: 0

`2.8.0`は今回の計画で宣言されたproduct baselineです。
repository内には複数の古いversion表記が残っているため、canonical versionの確立は
R3-027で行います。このtracker作成時にはversion表記を変更しません。

## Goals

- 長期保守性を改善し、変更の影響範囲を予測可能にする
- API、application orchestration、problem loading、judge、Docker操作、DB処理の責務を分離する
- `ProblemDefinition`、`ExecutionResult`、`JudgeResult`、`SubmissionResult`を中心にtyped boundaryを導入する
- timeout、終了status、stdout、stderr、artifactを失わずに表現する
- judgeの文字列衝突、exit status無視、曖昧な画像比較を解消する
- versioned problem schemaと一元化されたproblem repositoryを導入する
- public backend、private runner、frontend間のcontractを明確にする
- sandbox securityを維持・改善し、失敗時もfail-closedにする
- unit、integration、frontend、rootless Docker E2Eで回帰を検出できるようにする
- obsolete code、asset、script、dependency、version表記を安全に整理する

## Non-goals

- UIやvisual designの全面刷新
- public backendとDocker runnerを統合すること
- microservices化やdistributed system化
- 必要性が確認されていないframework migration
- design patternを導入すること自体を目的とした抽象化
- sandbox制限やrootless要件を緩和して実装を簡単にすること
- v2の内部Python API、内部runner protocol、DB内部構造の完全互換
- 各unitで承認されていないproduct behaviorの付随的な変更

外部利用者向けの移行が必要なpublic API変更は、R3-016で明示的に設計し、
影響と移行方法を記録します。

## Design direction

v3はpublic backendとprivate Docker runnerの分離を維持したmodular monolithとします。
新しいDI frameworkやservice分割を前提にせず、明示的な型と小さいinterfaceで責務を分けます。

```text
Browser / typed frontend client
              |
              v
       FastAPI DTO / HTTP mapper
              |
              v
      SubmitSolutionService
       |        |          |
       |        |          +--> ExecutionLogRepo
       |        |
       |        +--> RunnerGateway --> typed runner protocol
       |                                  |
       v                                  v
 ProblemRepo                     RunnerExecutionService
       |                                  |
       v                                  v
ProblemDefinition                Admission + SandboxExecutor
                                          |
                                          v
                               ContainerManager --> rootless Docker

ExecutionResult --> pure Judge --> JudgeResult --> SubmissionResult
```

中心となるdomain dataは次の責務を持ちます。

- `ProblemDefinition`: metadata、入力fixture、実行条件、judge specificationを型付きで保持する
- `ExecutionResult`: execution status、stdout、stderr、exit code、timeout、truncation、artifact、durationを保持する
- `JudgeResult`: typed verdictとtext/imageごとの判定結果、安全なreasonを保持する
- `SubmissionResult`: execution、judgment、保存されたIDと時刻をAPIへ渡す

主なboundaryは次のとおりです。名称は実装unitのレビューで調整できますが、責務は混在させません。

- `ProblemRepo`: schemaを検証し、immutableな`ProblemDefinition`を返す
- `RunnerGateway`: public backendからprivate runnerへの通信だけを担う
- `SubmitSolutionService`: problem取得、実行、判定、保存のuse caseを編成する
- `SandboxExecutor`: sandboxへの準備、実行、capture、cleanupを管理する
- `ExecutionLogRepo`: DB保存、transaction、retention境界を担う
- `Judge`: file I/Oを行わず、problemのjudge specificationと`ExecutionResult`から`JudgeResult`を返す

## Priority definitions

このpriorityは設計上の実施順序とv3 releaseへの重要度を示します。
[security tracker](../security/README.md)のseverityとは別の概念であり、
security severityが同じでも依存関係や設計上の影響によりpriorityは異なります。

### P0

v3の中核となる問題、判定の正確性、重大な設計上の問題、または後続作業の前提です。
可能な限り早期に対応し、依存するunitより先に完了させます。

### P1

保守性、信頼性、security、testabilityに大きく影響する高優先度項目です。
v3 release前に原則として完了させます。

### P2

重要ですが、P0/P1の完了後でも安全に対応できる中優先度項目です。
release条件から外す場合は理由と残存リスクを記録します。

### P3

cleanup、documentation、obsolete asset、release整合などの低優先度項目です。
原則v3 releaseまでに整理しますが、削除対象の代替実装が完了するまで待ちます。

## Status definitions

- `Planned`: scopeと順序は記録済みだが、依存関係またはreview gateが残っている
- `Ready`: 依存関係と必要な判断が揃い、承認後に実装を開始できる
- `In Progress`: 実装または検証中
- `Review`: Codexによる実装と予定したtestが完了し、依頼者のreview待ち
- `Completed`: 依頼者が承認し、対象commitが作成済み
- `Blocked`: 外部条件や未解決の判断により進行できず、解除条件を記録済み
- `Deferred`: 実施を意図的に後回しとし、理由と再評価条件を記録済み
- `Superseded`: 別unitまたは変更後の計画に置き換えられ、置換先と理由を記録済み

依頼者のreview前に`Completed`へ変更しません。
Codexが実装とtestを終えた時点は`Review`です。

## Roadmap overview

| ID | Priority | Status | Phase | Title | Dependencies | Completion commit |
| --- | --- | --- | --- | --- | --- | --- |
| R3-001 | P1 | Completed | A | Disable proxy inheritance for private runner client | - | `74a1a74` |
| R3-002 | P1 | Completed | A | Make Host, redirect, and proxy trust explicit | R3-001 | `6061ebc` |
| R3-003 | P1 | Completed | A | Make execution-log persistence non-blocking and failure-safe | - | `3843e37` |
| R3-004 | P1 | Completed | A | Align supported Python versions and concurrency behavior | - | `9510c1f` |
| R3-005 | P0 | Completed | A | Characterize legacy problem, judge, and frontend behavior | - | `79ca954` |
| R3-006 | P0 | Completed | B | Introduce v3 problem schema and migration tooling | R3-005 | `e710670` |
| R3-007 | P0 | Completed | B | Migrate all problem definitions to schema v3 | R3-006 | `4d25fa8` |
| R3-008 | P0 | Completed | B | Introduce immutable ProblemRepo and manifest digest | R3-007 | `6360c34` |
| R3-009 | P0 | Completed | B | Introduce typed runner execution protocol | R3-005 | `62dadf6` |
| R3-010 | P0 | Completed | B | Extract pure text judge and typed JudgeResult | R3-006, R3-009 | `91fdbad` |
| R3-011 | P0 | Completed | B | Separate and correct image judging | R3-007, R3-009 | `7947640` |
| R3-012 | P1 | Completed | C | Separate sandbox preparation, execution, capture, and cleanup | R3-009 | `370e5b8` |
| R3-013 | P0 | Completed | C | Capture structured execution outcomes | R3-012 | `97315a6` |
| R3-014 | P1 | Completed | C | Introduce ExecutionLogRepo and database migrations | R3-003, R3-009 | `b7cb6f9` |
| R3-015 | P0 | Completed | C | Introduce SubmitSolutionService | R3-008, R3-010, R3-011, R3-014 | `105ec70` |
| R3-016 | P1 | Completed | C | Expose typed public API v3 contract | R3-015 | `074f450` |
| R3-017 | P1 | Completed | C | Harden runner authentication, readiness, and revision checks | R3-008, R3-009 | `07545a5` |
| R3-018 | P2 | Completed | C | Add safe structured logging and request correlation | R3-015 | `45d5482` |
| R3-019 | P1 | Completed | D | Introduce typed frontend API client | R3-005, R3-016 | `82a19be` |
| R3-020 | P1 | Completed | D | Model frontend submission state and cancellation safely | R3-019 | `bc6e60c` |
| R3-021 | P2 | Completed | D | Consolidate frontend toolchain after behavior coverage | R3-020 | `872bacf` |
| R3-022 | P1 | Completed | E | Pin runtime artifacts and harden mounts and configuration | R3-013 | `eff33ca` |
| R3-023 | P1 | Completed | E | Split production backend and runner images | R3-017, R3-022 | `aacda56` |
| R3-024 | P1 | Completed | E | Add full rootless Compose E2E regression | R3-016, R3-017, R3-023 | `48a0670` |
| R3-025 | P2 | Completed | E | Harden CI and software supply-chain checks | R3-004, R3-022, R3-024 | `7b779b3` |
| R3-026 | P3 | Planned | F | Remove obsolete code, assets, scripts, and dependencies | replacement units | - |
| R3-027 | P3 | Planned | F | Establish canonical v3.0.0 version and release documentation | 自身を除く全release対象unit | - |
| R3-028 | P1 | Completed | D | Distinguish execution failures and judge errors in frontend results | R3-019, R3-020 | `eb9e458` |
| R3-029 | P2 | Planned | F | Organize shared, backend, and runner packages | R3-023, R3-024 | - |

Size estimates use `XS` (under about 100 changed lines), `S` (100--250),
`M` (250--600), and `L` (over 600 or a large mechanical data migration).
They are planning aids, not acceptance criteria.

## Phase A — Safe baseline

### R3-001: Disable proxy inheritance for private runner client

- Priority / Status: P1 / `Completed`
- Goal: private runnerへの固定内部HTTP通信が`HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`等を継承しないようにし、credentialとrequestの外部proxy送信を防ぐ
- Main files/components: `backend/scripts/runner_client.py`、`backend/tests/test_runner_boundary.py`、security tracker
- Dependencies: なし
- Risk: Low。内部clientに限定するが、timeout、Bearer認証、response size上限を維持する必要がある
- Expected tests: proxy環境変数を設定した境界test、runner client既存test、ruff、format、mypy、non-Docker pytest
- Size: XS
- Completion: commit `74a1a7474a02ab833f176be337b6ae5461252a4d` / date 2026-08-26 / environment proxy inheritance disabled without changing the runner request contract

### R3-002: Make Host, redirect, and proxy trust explicit

- Priority / Status: P1 / `Completed`
- Goal: trailing-slash redirect、Host、forwarded headerの信頼境界を明示し、外側proxy配下でも安全なURLを生成する
- Main files/components: `backend/main.py`、`frontend/nginx/default.conf`、public API test、運用文書
- Dependencies: R3-001
- Risk: Medium。既存URL、reverse proxy、health checkとの互換性を確認する
- Expected tests: ASGI redirect/Host test、nginx静的test、可能なら実nginx integration test
- Size: S
- Completion: commit `6061ebc9c4f186b9ea35e886eb8c2fcc9fc52f8f` / date 2026-08-26 / slash redirects disabled and the backend Host and forwarded-header trust boundary fixed

### R3-003: Make execution-log persistence non-blocking and failure-safe

- Priority / Status: P1 / `Completed`
- Goal: NUL等の保存不能値、DB stall、commit失敗がevent loop停止やrollback漏れを起こさない境界を先に整える
- Main files/components: `backend/api/api_shellgei.py`、`backend/scripts/database.py`、retention処理、DB test
- Dependencies: なし
- Risk: Medium--High。保存内容とHTTP応答、既存DBのtransaction behaviorへ影響する
- Expected tests: SQLite unit、NUL正規化、timeout/rollback、実PostgreSQL failure/recovery integration test
- Size: M
- Completion: commit `3843e379d4f926098f563e7b5df9d914e2341ed8` / date 2026-08-26 / execution-log persistence moved off the event loop with storage normalization, bounded PostgreSQL operations, and rollback-safe failure handling

### R3-004: Align supported Python versions and concurrency behavior

- Priority / Status: P1 / `Completed`
- Goal: 宣言するPython対応範囲、CI、production imageを一致させ、Python 3.14で確認されたtimeout/concurrency差異を解消または明示的に対象外とする
- Main files/components: `pyproject.toml`、CI workflow、`backend/scripts/run_shellgei.py`、関連test、開発文書
- Dependencies: なし
- Risk: Medium。support policyまたは並行実行のcleanup timingを変更する可能性がある
- Expected tests: 対応Python matrix、concurrency/timeout test、基本Python検査一式
- Size: S--M
- Completion: commit `9510c1f33ec3a04c67c0dd5f12aec40146509a69` / date 2026-08-27 / Python 3.12--3.14 support, CI matrix, and polling-based thread future completion behavior aligned

### R3-005: Characterize legacy problem, judge, and frontend behavior

- Priority / Status: P0 / `Completed`
- Goal: 意図した互換性と修正対象を区別できるよう、現行problem、judge、API/frontend表示のcharacterizationを実装前の回帰基準として固定する
- Main files/components: backend judge/problem test、frontend API/UI test、92問のsemantic manifest、[v3移行前のbehavior baseline](./legacy-behavior.md)
- Dependencies: なし
- Risk: Low。production behaviorは変えないが、誤判定を期待値として固定しないよう「既知の不具合」を明示する
- Expected tests: judge truth table、problem corpus検査、frontend mock response、既存non-Docker test
- Size: M
- Completion: commit `79ca954e3f23ce851aae1812637d5bf5b2371fd0` / date 2026-08-28 / legacy problem corpus, judge behavior, frontend API/display behavior, and known defects characterized

## Phase B — Domain / Problem / Judge

### R3-006: Introduce v3 problem schema and migration tooling

- Priority / Status: P0 / `Completed`
- Goal: schema version、execution input/fixture、judge type、exit/stderr policy、artifactを明示する型付きproblem schemaを導入する
- Main files/components: problem domain model、schema validator、migration tool、`problems/README.md`、代表problem 3件程度
- Dependencies: R3-005
- Risk: Medium。既存problemの暗黙的な意味を誤って変換しないこと
- Expected tests: valid/invalid schema、duplicate/extra/missing field、path/size/image制約、pilot problem回帰
- Size: M
- Completion: commit `e7106708320b9a29066c26bed081fcb655493f1c` / date 2026-08-30 / typed schema v3, strict YAML validation, deterministic legacy migration, and three pilot problems introduced without changing the production read path

### R3-007: Migrate all problem definitions to schema v3

- Priority / Status: P0 / `Completed`
- Goal: 全92問をv3 schemaへ機械的に移行し、text/image judge、fixture、入力を明示する
- Main files/components: `problems/v3/*.yaml`、fixture、problem migration検査、全問題Docker回帰
- Dependencies: R3-006、reference solution公開方針のreview gate
- Risk: Medium。差分量が大きく、問題文や正解データの意図しない変更を見落としやすい
- Expected tests: 全problem schema検証、移行前後semantic manifest、代表実行、全問題回帰
- Size: L
- Completion: commit `4d25fa8f19b790a5951a06ae0858c794417b3ea2` / date 2026-08-30 / all 92 problems migrated deterministically with legacy semantic equality and rootless Docker answer regression verified

### R3-008: Introduce immutable ProblemRepo and manifest digest

- Priority / Status: P0 / `Completed`
- Goal: YAML/imageの重複読込を一元化し、startup時に検証済みのimmutableな`ProblemDefinition`とproblem data revisionを提供する
- Main files/components: problem catalog/repository、backend startup、runner startup、problem API/judge caller
- Dependencies: R3-007
- Risk: Medium。cache lifetime、startup failure、backend/runner間のdata不一致を正しく扱う必要がある
- Expected tests: startup validation、immutable lookup、missing/corrupt data、manifest digest一致/不一致
- Size: M
- Completion: commit `6360c343aa4d61771794d0fdb8fe2a29006f28ca` / date 2026-08-30 / startup-validated immutable problem repository, canonical manifest revision, and v3 production read path introduced

### R3-009: Introduce typed runner execution protocol

- Priority / Status: P0 / `Completed`
- Goal: runner応答を`[output, image]`やmagic stringからtyped `ExecutionResult`へ移行できる内部protocolを定義する
- Main files/components: runner request/response model、`RunnerGateway`、runner endpoint、protocol test
- Dependencies: R3-005
- Risk: Medium。public backendとrunnerを同時に移行し、size limitと認証を維持する必要がある
- Expected tests: serialization、unknown field/version、response size、timeout/unavailable、互換移行境界
- Size: M
- Completion: commit `62dadf668a17dc1f43bdd73cd91c1d03eb594b54` / date 2026-08-30 / versioned strict request/response models, typed ExecutionResult, and RunnerGateway introduced without changing the public API

### R3-010: Extract pure text judge and typed JudgeResult

- Priority / Status: P0 / `Completed`
- Goal: file I/Oをjudgeから除き、token置換/`NULL`衝突をなくして、明示的なnewline・space・stderr・exit policyでtext verdictを返す
- Main files/components: judge domain model、pure text judge、problem judge specification、judge test corpus
- Dependencies: R3-006、R3-009
- Risk: High。現在の誤ったacceptを含む判定結果が変わるため、意図したbreaking changeの確認が必要
- Expected tests: whitespace truth table、token literal、empty/`NULL`、non-zero exit、stderr、timeout/truncation、全text problem回帰
- Size: M
- Completion: commit `91fdbad3e958a0dfcc6069a0da8cd90bef325f6c` / date 2026-08-30 / pure typed text judge, collision-free comparison, explicit execution policies, and legacy public code mapping introduced

### R3-011: Separate and correct image judging

- Priority / Status: P0 / `Completed`
- Goal: text問題から暗黙の画像判定を除き、artifact MIME/pathと画像比較方式をschemaで明示し、先頭byte除外による誤判定をなくす
- Main files/components: image judge、artifact model、problem schema、runner capture、frontend contract
- Dependencies: R3-007、R3-009、image comparison strategyのreview gate
- Risk: High。既存5画像問題、JPEG/GIF、表示MIME、正規化方針へ影響する
- Expected tests: exact/corrupt/header-only差分、JPEG/GIF MIME、missing/multiple artifact、5画像問題回帰
- Size: M--L
- Decision: 比較方式の決定と理由は[review gate一覧](#open-decisions--review-gates)、現行判定規則は[問題データ](../../problems/README.md#schema-v3)を参照
- Completion: commit `7947640e9ae452c8a41c33391fcc222aee9af5a4` / date 2026-08-30 / schema-selected typed artifacts, strict JPEG/GIF validation, exact-pixel judging, MIME-aware public response and frontend display introduced

## Phase C — Execution / Application / API

### R3-012: Separate sandbox preparation, execution, capture, and cleanup

- Priority / Status: P1 / `Completed`
- Goal: archive準備、container割当、exec、watchdog、出力capture、破棄を小さい責務へ分け、raceとresource leakを検証可能にする
- Main files/components: execution archive、`SandboxExecutor`、`ContainerManager`、runner service
- Dependencies: R3-009
- Risk: High。Docker lifecycleとsecurity invariantを変更するため、timeout/例外時も必ずfresh containerを破棄する必要がある
- Expected tests: fake Docker unit、create/start/exec/capture/cleanup failure、concurrency、Docker lifecycle integration
- Size: M
- Completion: commit `370e5b8da6cd50a322a5b43ddc162bb0ba1674e4` / date 2026-08-31 / `SandboxPreparer`、
  `SandboxOutputCapturer`、`ExecutionWatchdog`、`SandboxCleanup`、
  `SandboxExecutor`へ責務を分離し、timeout側killの完了後に停止済み返却する同期を追加。
  fake Docker failure unit、Python 3.14の非Docker 418件、rootless Docker integration
  7件が成功。full problem regression 1件は明示flag未指定のためskip

### R3-013: Capture structured execution outcomes

- Priority / Status: P0 / `Completed`
- Goal: exit code、stdout、stderr、timeout、truncation、duration、binary artifactを別々にcaptureして`ExecutionResult`を完成させる
- Main files/components: Docker exec adapter、capture limits、artifact reader、execution model
- Dependencies: R3-012
- Risk: High。memory/output limit、background process、binary data、cleanup順序の回帰を避ける
- Expected tests: exit/stderr分離、invalid UTF-8、NUL、byte/character limit、timeout、background writer、Docker/full regression
- Size: M--L
- Completion: commit `97315a6c7da671dc4c5ff9a6441210443bf69d97` / date 2026-09-01 / internal runner protocolをversion 3へ更新し、
  status、stdout、stderr、exit code、timeout、切り詰め、所要時間、binary artifactを
  分離して取得する`ExecutionResult`を導入。既存public APIでは互換表示へ変換し、
  typed judgeへ構造化結果を直接渡す。Python 3.14の非Docker 428件、rootless Docker
  lifecycle・全92問回帰を含む9件が成功

### R3-014: Introduce ExecutionLogRepo and database migrations

- Priority / Status: P1 / `Completed`
- Goal: persistenceをapplication/APIから分離し、typed resultを安全に保存できるschema、migration、transaction、retention境界を導入する
- Main files/components: DB model、`ExecutionLogRepo`、migration、retention、database test
- Dependencies: R3-003、R3-009、execution log retention/privacyのreview gate
- Risk: Medium--High。既存volume/data migrationとrollback、保持policyに影響する
- Expected tests: forward/rollback migration、transaction failure、retention、real PostgreSQL integration
- Size: M
- Completion: commit `b7cb6f90833801573689973ecabf257bdfdcd0d3` / date 2026-09-01 / `ExecutionLogRepo`とartifact・request情報を
  受け取らないtyped保存entry、version table・advisory lock付きforward/rollback migrationを
  導入。legacy列を保持して構造化実行・判定列を追加し、backend起動前migration、同一transactionの
  retention、失敗時rollbackを実装。request単位のnginx/Uvicorn access logも無効化した。
  Python 3.14の非Docker 439件、rootless PostgreSQL migration/recovery 1件、実nginx 1件、
  rootless Compose configが成功

### R3-015: Introduce SubmitSolutionService

- Priority / Status: P0 / `Completed`
- Goal: problem取得、runner実行、判定、保存をtyped use caseへ集約し、HTTP handlerをtransport mappingだけにする
- Main files/components: application service、domain result、ProblemRepo/RunnerGateway/Judge/ExecutionLogRepo ports、API handler
- Dependencies: R3-008、R3-010、R3-011、R3-014
- Risk: Medium。error mappingと保存順序を維持しつつ、infrastructure failureをwrong answerから分離する
- Expected tests: fake portsによるsuccess/not-found/busy/timeout/judge/persistence failure、call ordering
- Size: M
- Completion: commit `105ec70e3594bcafb2699f9aa950c0bcc389368e` / date 2026-09-01 / `SubmissionResult`、ProblemRepo・
  RunnerGateway・Judge・ExecutionLogRepoのport、`SubmitSolutionService`を導入。
  problem確認、実行、判定、保存の順序をHTTP handlerから分離し、未登録、runner混雑・停止、
  timeout、judge例外、保存失敗をfake port testで検証。既存public response形式を維持し、
  Python 3.14の非Docker 446件とruff・format・mypyが成功

### R3-016: Expose typed public API v3 contract

- Priority / Status: P1 / `Completed`
- Goal: request/response DTO、typed verdict、execution failure、artifact MIME、HTTP statusを明文化しfrontendとのcontractを固定する
- Main files/components: FastAPI route/model、OpenAPI、HTTP mapper、API documentation
- Dependencies: R3-015
- Risk: Medium。public contractのbreaking changeとfrontend移行を同期する必要がある
- Expected tests: ASGI 200/404/422/429/503、OpenAPI schema、response size/cache/security header
- Size: M
- Completion: commit `074f450bf65a2e7b5087d510485fe6e12574acfc` / date 2026-09-02 / legacy `/api/shellgei`を維持しながら
  `/api/v3/submissions`、strict request DTO、typed verdict・reason・execution・artifact・
  persistence response、404・422・429・503 contractを追加。内部errorとartifact pathを除外し、
  response byte上限、no-store・nosniff、Retry-Afterを実装してOpenAPIとASGIで検証。
  Python 3.14の非Docker 457件、ruff・format・mypy、rootless実nginx 1件が成功。
  frontend JavaScriptは未変更だが、Node.js・Yarnが環境になくfrontend検査は未実行

### R3-017: Harden runner authentication, readiness, and revision checks

- Priority / Status: P1 / `Completed`
- Goal: request body parse前にrunner認証を行い、pool劣化をreadinessへ反映し、protocol/problem revision不一致をfail-closedにする
- Main files/components: runner middleware/endpoint、health/readiness、RunnerGateway、Compose healthcheck
- Dependencies: R3-008、R3-009
- Risk: Medium。ASGI request処理順、起動中のreadiness、rolling update互換性へ影響する
- Expected tests: unauthorized large body、body limit、degraded pool、protocol/data digest mismatch、restart behavior
- Size: M
- Completion: commit `07545a5573208084f8a505fbad44b0f872826336` / date 2026-09-03 / 実行requestをASGI middlewareでbody読込前に
  Bearer認証し、認証後bodyを8 KiBへ制限。backendとrunnerのproblem dataの
  SHA-256 revisionをrequest/responseで相互検証し、requestの不一致は実行前に拒否し、
  responseの不一致も受理しないようにした。
  revisionの算出対象は[問題データ](../../problems/README.md#problem-data-revision)を参照。
  livenessとreadinessを分離し、pool削除・補充失敗後は再起動まで非readyを維持する。
  Compose healthcheckをreadinessへ変更し、Python非Docker test 473件、
  rootless Docker test 8件、Compose設定検査、ruff、format、mypyが成功。

### R3-018: Add safe structured logging and request correlation

- Priority / Status: P2 / `Completed`
- Goal: public APIからrunner/DBまでrequest IDと安全なstatus/durationを追跡し、command、output、secretを不用意にlogしない
- Main files/components: logging configuration、middleware、application/runner events、運用文書
- Dependencies: R3-015
- Risk: Low--Medium。sensitive data漏えいとlog cardinality増加を防ぐ
- Expected tests: correlation propagation、redaction、no raw command/output/secret、failure event coverage
- Size: S--M
- Completion: commit `45d54829bec441db75c0962023a7398debd2ace4` / date 2026-09-03 / backendで提出ごとに128-bit request IDを
  生成し、public response、application context、runner request/response、DB保存eventへ伝播。
  client指定IDは無視し、request IDもDB行には保存しない。request単位eventを
  allowlist型JSONとし、command、stdout/stderr、problem ID、例外文、secret、IP、headerを
  schemaが受け付けないことを回帰testで固定。Python非Docker test 493件、
  ruff、format、mypyが成功。sandbox・Docker・Compose設定は変更していない。

## Phase D — Frontend

### R3-019: Introduce typed frontend API client

- Priority / Status: P1 / `Completed`
- Goal: raw `fetch`、tuple、`any`、magic verdict判定をtyped clientと明示的なDTO mappingへ置き換える
- Main files/components: frontend API client/types、problem/result functions、component props、API mock
- Dependencies: R3-005、R3-016
- Risk: Medium。表示上の互換性とAPI移行期間を管理する必要がある
- Expected tests: typed success/error fixtures、unknown verdict、artifact MIME、problem selection、lint/type/build
- Size: M
- Completion: commit `82a19be374f7d6f2511e9d223481a1eae3a65929` / date 2026-09-03 / `fetch`を単一clientへ集約し、提出を
  `/api/v3/submissions`へ移行。成功・HTTP error・problem responseを`unknown`から
  runtime検証し、typed verdict、分離execution、JPEG/GIF artifactを明示的に画面へ
  mappingする。legacy tuple、数字judge code、`any`、frontendのlegacy提出呼出しを削除。
  frontend test 21件、format、lint、production buildがrootless Docker上で成功。

### R3-020: Model frontend submission state and cancellation safely

- Priority / Status: P1 / `Completed`
- Goal: submission stateをdiscriminated unionで表し、`AbortController`、duplicate防止、selection/response race、timeout表示を正しく扱う
- Main files/components: React state/hooks、submit/result components、API cancellation、frontend test
- Dependencies: R3-019
- Risk: Medium。非同期UI behaviorと既存操作感へ影響する
- Expected tests: timeout/abort、double submit、out-of-order response、selection race、latest request wins、JPEG/GIF表示
- Size: M
- Completion: commit `bc6e60c156a1617e19dfc6414c60988e61f169cd` / date 2026-09-03 / 提出表示を`idle`、`running`、
  `succeeded`、`failed`、`validation_error`のdiscriminated unionへ統合。
  timeout、差し替え、component破棄でfetch本体をabortし、同一提出の二重送信を抑止。
  異なる新規提出と問題選択は世代番号で最新responseだけを反映し、abortを無視する
  fetchでも旧結果を破棄する。frontend test 26件、format、lint、production buildが
  rootless Docker上で成功。

### R3-021: Consolidate frontend toolchain after behavior coverage

- Priority / Status: P2 / `Completed`
- Goal: behavior testを先に確保した後、維持可能なbuild/test/lint/typecheck構成へ統合し、必要ならdeprecatedなCRAから移行する
- Main files/components: frontend package/build config、test setup、Dockerfile、frontend documentation
- Dependencies: R3-020、Analytics/Google Fonts/CSPのreview gate
- Risk: Medium。build artifact、environment variable、nginx配信、browser behaviorが変わり得る
- Expected tests: format、lint、typecheck、unit/component test、production build、nginx smoke
- Size: M
- Completion: commit `872bacfe4aef87ab9812afbfe7c4b6fa5defe652` / date 2026-09-04 / CRAをVite、JestをVitestへ移行し、
  ESLint 10のflat config、TypeScript型検査、CI、Docker buildを同じtoolchainへ統合。
  `REACT_APP_*`を`VITE_*`へ移し、Google AnalyticsとGoogle Fontsを削除して
  same-origin CSPを追加。frontend test 26件、format、lint、typecheck、production build、
  Python非Docker test 495件、ruff、format、mypy、Compose設定、rootless実nginx smokeが成功

### R3-028: Distinguish execution failures and judge errors in frontend results

- Priority / Status: P1 / `Completed`
- Goal: backendが区別した実行失敗・判定エラーをfrontendで不正解へ潰さず表示する
- Main files/components: `frontend/src/functions/judge_result.tsx`、`submit.tsx`、`legacy_behavior.test.jsx`、frontend README、legacy behavior文書
- Dependencies: R3-019、R3-020
- Scope: 既存public APIのverdict・reasonを固定表示文言へmappingする。backend、API schema、受付・通信・非同期stateは変更しない
- Expected tests: 旧失敗表示の期待値変更でRED、API clientからDOMまでの実行失敗・判定エラー・timeout・出力上限、終了code許容問題、未知reason拒否、frontend基本5検査
- Risk: Low。利用者向け判定文言が変わるため、HTTP応答成功と実行成功を混同しない
- Size: S
- Completion: commit `eb9e4587badc3bbfd1e48712a7afc5b5e1daf1d5` / date `2026-09-05` / 依頼者のreview承認後にcommit済み。
  表示期待値の修正後、実装前に9件のREDを確認。rootless Dockerの既存builder
  （Node.js 22.23.2 / Yarn 1.22.22）で現ソースを一時コピーし、frontend test 35件、
  format、lint、typecheck、production buildが成功。二重送信・abort・response raceの
  既存testも成功。backend contract・sandbox変更がないためPython/Docker問題回帰は未実行

## Phase E — Runtime / Supply Chain / E2E

### R3-022: Pin runtime artifacts and harden mounts and configuration

- Priority / Status: P1 / `Completed`
- Goal: imageをdigestで固定し、sandboxの予期しないmount/volumeを拒否し、nginx設定等のwritable bind mountをなくす
- Main files/components: Compose、Dockerfiles、ContainerManager validation、nginx configuration、security documentation
- Dependencies: R3-013
- Risk: High。image更新手順、rootless runtime、sandbox startupを変更する
- Expected tests: Compose静的test、image inspect、mount/volume rejection、rootless Docker baseline/full regression
- Size: M
- Completion: commit `eff33ca96d6865055fb421c7de7ea43da62c2ce7` / date 2026-09-04 / sandbox、Python、Node.js、nginx、PostgreSQL imageをdigest固定し、
  sandbox imageの`VOLUME`と作成後の予期しないmountをfail-closedで拒否。
  frontend nginx設定をimageへ組み込み、匿名volume cleanupと更新手順を追加。
  Python test 506件、frontend test 26件、image build、Compose設定、rootless Docker test 8件、
  全92問回帰が成功

### R3-023: Split production backend and runner images

- Priority / Status: P1 / `Completed`
- Goal: backendとrunnerのruntime image/dependencyを分け、non-rootとleast privilegeを適用し、productionへtest/development dependencyを持ち込まない
- Main files/components: backend/runner Dockerfile targets、dependency groups、Compose、runtime image tests、deployment docs
- Scope: 現行の同一rootless daemon構成でOS user・image・依存を分離する。専用host/VM移設とDB owner/app role分離は含めず、SOJ-006・SOJ-011の残存課題として追跡する
- Dependencies: R3-017、R3-022、runner専用host/VM判断のreview gate
- Risk: High。Docker socket access、UID/GID、rootless運用、build/release artifactへ影響する
- Expected tests: reproducible image build、user/dependency inspection、runner socket access、backend socket非保持、Compose integration
- Size: M--L
- Review validation: 2026-09-05、実装前に依存・Compose境界testの2件のREDを確認。
  Python 3.14でruff・format・mypy・非Docker 508件、rootless Docker既存9件（全92問回帰を含む）、
  build済みPython 3.12の本番image検査4件が成功。新image検査は別flagで実行したため、
  既存Docker回帰の実行では同4件をskip。両targetのbuild、GID設定済みComposeと未設定時の拒否を確認。
  frontendのコード・toolchainは変更していないためfrontend基本検査は再実行していない。
- Completion: commit `aacda5640b87157ab2aa06c1f8d329250e51f289` / date 2026-09-05 / 依頼者のreview承認後にcommit済み。専用host/VM移設とDB role分離は残存課題として維持する

### R3-024: Add full rootless Compose E2E regression

- Priority / Status: P1 / `Completed`
- Goal: frontend/nginxからbackend、runner、rootless Docker、PostgreSQLまでの実経路を自動検証する
- Main files/components: `backend/tests/compose_support.py`、`test_compose_e2e.py`、browser専用Dockerfile/script、任意のPoetry e2e group、integration documentation
- Dependencies: R3-016、R3-017、R3-023。recoveryは既存のrunner再起動と起動時回収を対象とする
- Risk: High。専用rootless Docker環境と安全なcleanupが必要で、通常hostで破壊的耐性試験を行わない
- Expected tests: success/wrong/execution failure、auth/revision mismatch、restart/recovery、DB persistence、frontend proxy、full problem regression
- Size: M
- Implemented scope: 本番Compose定義からtest projectを生成し、実TLS nginx・backend・runner・DBを起動する。
  project名・owner・credential・DB volume・公開portを分離し、本番制約を維持する。
  browserは独立したtest imageで実UIを操作する。通常の依存導入・本番targetにはPlaywrightを含めない。
  Docker経由のSIGKILL後の明示再起動・旧sandbox回収と、processのSIGTERM終了後の自動再起動を分けて検証する。
  起動前の隔離検査と、部分失敗時も残るcleanupを試みる仕組みを追加した。
- Review validation: 2026-09-05、Python 3.14のruff・format・mypy・非Docker 527件、
  rootless Docker 19件（Compose E2E 6件、既存統合/全問題回帰9件、本番image検査4件）が成功。
  全92問は既存sandbox回帰とnginx経由のCompose回帰の両方で検証した。
  frontendのformat・lint・typecheck・test 35件・production buildが成功。
  backend/runner/frontend/browserの4 imageをbuildし、rootless wrapper経由のCompose設定検査も成功。
  最終cleanup順序の補強後もCompose基本5件が成功し、専用資源の残存がないことを確認した。
  独立reaper・本番host・外側proxy・破壊的耐性試験は対象外。既存のFastAPI/Python・React Routerの警告は残る。
- Completion: commit `48a067086315f9fe06697dbcfd357568483d8ebf` / date 2026-09-05 / 依頼者のreview承認後にcommit済み。独立reaperとCI整備は今回の対象外として維持する

### R3-025: Harden CI and software supply-chain checks

- Priority / Status: P2 / `Completed`
- Goal: CI token権限、timeout、supported runtime matrix、dependency/image/secret scan、SBOM、artifact provenanceを段階的に導入する
- Main files/components: `.github/workflows/`、dependency update policy、image build/promotion、security documentation
- Dependencies: R3-004、R3-022、R3-024
- Risk: Medium。external scannerのavailability、false positive、artifact release flowを管理する必要がある
- Expected tests: workflow validation、least-permission review、scanner fixtures、SBOM/provenance generation、required checks
- Size: M
- Implemented scope: 既存CIのAction SHA・権限・timeout・concurrency・Poetry/Yarnを固定し、
  専用workflowへsecret/lock file/image scan、SBOM、rootless Compose E2E、main限定の署名jobを追加。
  scannerはversionと配布hashを固定し、依存更新はDependabotの週次PRでreviewする。
  配布候補archiveはscan済みのimmutable IDから保存し、未署名recordにsource commitとfile hashを記録する。
  手順・停止条件・保証範囲の正本は[CI文書](../CI.md)。remote設定や本番deployは変更していない。
- Review validation: 2026-09-05、実装前にCI policy test 2件のREDを確認。
  actionlint、Pythonのruff・format・mypy・非Docker 541件、frontend基本5検査（test 35件）が成功。
  公式archiveでinstallerのhash照合、実scannerで合成secret・既知脆弱package・破損SBOMの検出を確認。
  Git履歴160 commitsのsecret scanは検出なし。lock fileのSBOMと既存の本番3 image・
  正本のDB/sandboxのSBOM・脆弱性reportを生成し、候補archiveのOCI indexとscan済みID、全file hashを照合した。
  imageはR3-024でbuild・検証済みのものを使用。GitHub-hosted上の新規build・rootless setup・
  OIDC署名・required checksは未実行で、反映後の確認が必要。Docker実行コードと問題dataは変更していないため、
  既存Docker 19件・全92問回帰は今回は再実行していない。
- Scan findings: 停止対象（修正版のあるHigh/Critical）はlock file 12、backend 6、runner 8、
  frontend 20、DB 42、sandbox 248件。対象ごとのmatch数であり、重複を除いたCVE数ではない。
  scan処理とreport生成は完了したが、gateは設計どおり終了code 2となるため、現状のCIは成功扱いにならない。
  到達性・false positiveの評価と更新はSOJ-022へ登録し、R3-025では既存検出のbaseline化やignore追加を行っていない。
- Completion: commit `7b779b3` / date `2026-09-05` / note 依頼者のreview・commit承認により完了。検出済み脆弱性とGitHub上の運用確認はSOJ-022・SOJ-019で継続追跡する。

## Phase F — Cleanup / Release

### R3-029: Organize shared, backend, and runner packages

- Priority / Status: P2 / `Planned`
- Goal: `scripts/`・`models/`へ混在している共有・backend専用・runner専用コードを責務別のdirectory/packageへ整理し、Dockerfileのfile単位COPY列挙をdirectory単位のCOPYへ置き換える
- Main files/components: `backend/`のpackage構成・import、`backend/Dockerfile`、entrypoint、migration CLI、test・CI設定、backend/development/production文書
- Dependencies: R3-023、R3-024。image境界と実Compose経路の回帰基準を確保してから移動する
- Scope: directory名・配置は着手時にimport依存を調査して決める。共有packageが専用API・DB・Docker実装へ依存しない境界を明示し、必要なmodel分離とimport修正を行う。不要資産の削除はR3-026と区別する
- Acceptance: file追加ごとにDockerfileの列挙を修正せずに済み、各imageへ逆側の専用コードやtestが混入しない。公開API、runner protocol、判定、DB schema、sandbox制限を維持する
- Risk: Medium。import漏れ、循環import、問題dataの相対path、起動・migration commandの破損を防ぐ
- Expected tests: packageのimport方向・収録境界、両本番imageのbuild/import/非root起動、migration CLI、基本Python検査、rootless Compose E2E・Docker統合・全問題回帰、文書commandとlink検査
- Size: M--L
- Completion: commit `-` / date `-` / note `-`

### R3-026: Remove obsolete code, assets, scripts, and dependencies

- Priority / Status: P3 / `Planned`
- Goal: 代替経路の完了後にdead code、unused CSS/image/script、manual regression重複、不要なruntime dependencyを削除する
- Main files/components: `backend/scripts/`、`deploy/`、frontend asset/CSS、Python/frontend dependency manifests、関連README
- Dependencies: 各削除対象を置き換えるR3 unit。削除前に使用箇所を再調査する
- Risk: Low--Medium。運用で暗黙に使われているscriptやassetを削除しないこと
- Expected tests: repository-wide reference search、基本Python/frontend検査、build、Compose test、documentation link check
- Size: M
- Completion: commit `-` / date `-` / note `-`

### R3-027: Establish canonical v3.0.0 version and release documentation

- Priority / Status: P3 / `Planned`
- Goal: versionの正本を決め、API/UI/package/image/release metadataを`3.0.0`へ揃え、migration・deployment・rollback・release noteを完成させる
- Main files/components: version metadata、frontend display、OCI label、README、development/production/security/problem docs、update history
- Dependencies: 自身を除く全release対象unit（R3-028・R3-029を含む）が`Completed`、または未完了unitのdefer判断が承認済み
- Risk: Low。version表記漏れとrelease artifact不一致を防ぐ
- Expected tests: canonical version assertion、API/UI/OCI consistency、documentation commands、全基本検査、rootless Compose E2E/full regression
- Size: S
- Completion: commit `-` / date `-` / note `-`

## Known design decisions

- public backendとDocker runnerの分離を維持する
- Docker socketはprivate runnerだけに接続し、public backendへ戻さない
- rootless Dockerを必須とし、rootful/TCP daemonへ暗黙にfallbackしない
- sandboxのnetwork、capability、PID、CPU、memory、filesystem、timeout、output制限をリファクタリング都合で弱めない
- request間でcontainer、一時data、出力、状態を共有しない
- judgeをfile I/O、problem loading、HTTP、DBから分離し、`ExecutionResult -> JudgeResult`をpureな境界にする
- versioned problem schema v3と、一元化されたimmutable `ProblemRepo`を導入する
- v2内部Python API、runner protocol、DB内部構造の完全互換は要求しない
- public APIのbreaking changeはR3-016で明示し、frontendと同期して移行する
- microservices化、新しいDI framework、不要なdependency/framework migrationは避ける
- security上の互換性変更は、理由、影響、代替案、fail-closed behavior、testをunit内で記録する

## Open decisions / Review gates

`Decision`と`Rationale`が空のgateを必要とするunitは、gateを解決するまで`Ready`にしません。

| Topic | Status | Decision needed before | Decision | Rationale |
| --- | --- | --- | --- | --- |
| R3-023でrunnerを専用hostまたは使い捨てVMへ分離するか | Decided | R3-023の最終設計 | このunitは現行の同一rootless daemon構成でimage・OS user・依存を分離する。host/VM移設はSOJ-006としてDeferredを維持し、v3 release範囲確定時に再評価する | 別hostへの移設は内部HTTPの暗号化・認証と本番基盤の設計を伴うため、image分離と同時には変更しない。2026-09-05、既存構成を維持する範囲で実装 |
| runner process外の独立reaperを導入するか | Decided | R3-024のrecovery acceptance確定 | R3-024はrunner再起動時の旧sandbox回収とservice停止復帰を検証する。独立した期限強制はSOJ-002の部分解決として維持する | 独立reaperはsocket権限と本番監視設計を追加するため、既存Compose経路の回帰確立と分ける。2026-09-05、既存の保証範囲を変更せず実装 |
| Analytics / Google Fontsを維持するか、CSPをどう設定するか | Decided | R3-021 | Google Analyticsと外部Google Fontsを削除し、script・style・font・API通信を同一originに限定するCSPを適用する。実行結果画像の`data:`だけを追加許可する | commandと結果を扱うbrowserから第三者への自動送信経路をなくし、外部resource障害と情報漏えい時の影響を減らす。2026-09-04決定、commit `872bacf` |
| reference solutionをpublic frontend/API artifactに含めるか | Decided | R3-007 | 現行どおりpublic problem detail APIで公開する | 既存APIは`answer`をすでに公開しているためR3-016以前の互換性を維持し、v3では`reference_solution`として保持する。2026-08-30決定、commit `4d25fa8` |
| execution logの利用目的、保持期間、privacy、backup方針 | Decided | R3-014 | 投稿ID発行、障害・security・不正利用調査に用途を限定し、保存対象とretention・backup policyを明示する。現行仕様は[実行ログとDockerログ](../../SECURITY.md#実行ログとdockerログ)を参照 | 漏えい時の影響を抑えるため個人特定につながるrequest情報と不要なbinaryを永続化せず、既存の保持上限とcommand・上限付き出力の互換性は維持する。2026-09-01決定、commit `b7cb6f9` |
| imageをbyte exact、canonicalized、pixel比較のどれで判定するか | Decided | R3-011 | `exact_pixels`を採用。現行規則は[問題データ](../../problems/README.md#schema-v3)を参照 | encoder metadataの差を許容しつつ、decode後の画素の差を見逃さないため。2026-08-30決定、commit `7947640` |

判断時は、該当行のstatusを`Decided`にし、決定内容、理由、日付、関連commitまたはissueを
`Decision`と`Rationale`へ記録します。v3範囲外とする判断も、無言で削除せず理由を残します。

## Known baseline issues

2026-08-25の調査時点で確認した主要な設計課題です。
security課題のseverity、詳細な防御、残存リスクは
[セキュリティ課題tracker](../security/README.md)を正本とし、ここでは重複して管理しません。

| Area | Baseline issue | Planned units |
| --- | --- | --- |
| Execution boundary | timeout、busy、unavailable、output limit等が通常の文字列へ潰れ、正常出力と区別できない | R3-009、R3-013、R3-015、R3-016 |
| Text judge | token置換と`NULL`表現が実出力と衝突し、末尾空白/newline規則も処理順依存 | R3-005、R3-010 |
| Process result | stdout/stderrが混在し、non-zero exit codeを判定に使わないため誤acceptし得る | R3-009、R3-010、R3-013 |
| Image judge | text問題にも画像比較を行い、先頭byteを除外した比較とJPEG/GIF contractが曖昧 | R3-007、R3-011、R3-013 |
| Problem data | versioned schemaがなく、judge type、exit/stderr policy、fixture、artifactが暗黙的 | R3-006、R3-007 |
| Problem loading | list、detail、runner input、judge expected dataが別々にYAML/imageを読む | R3-008 |
| Public API | handlerがvalidation、runner呼出し、judge、DB保存、retention、response生成を編成する | R3-015、R3-016 |
| Database | synchronous DB処理がasync request pathを塞ぎ、NUL、stall、rollback/migration境界が弱い | R3-003、R3-014 |
| Frontend contract | raw tuple/`any`/magic verdictに依存し、infrastructure errorをwrong answerとして表示し得る | R3-019、R3-020、R3-028 |
| Frontend async | client-side timeoutがfetchをabortせず、duplicate submissionとselection/response raceがある | R3-020 |
| Runtime matrix | 宣言範囲に含むPython 3.14でtimeout/concurrency testが失敗し、CIとproduction Pythonも異なる | R3-004 |
| Versioning | product baseline、tag、Python package、frontend package、UI環境変数にversion driftがある | R3-027 |
| Validation depth | backend/frontend/full Composeを通す自動E2Eと十分なfrontend behavior testがない | R3-005、R3-024、R3-025 |

## Unit update rules

### Starting a unit

1. baseline以降の差分、関連unit、open review gate、security trackerを再確認する
2. scope、main files、risk、expected testsが現在も妥当か更新する
3. 依頼者の実装承認後、statusを`Ready`から`In Progress`へ変更する

### Requesting review

1. 実装と文書同期を完了する
2. expected testsを実行し、未実行/skip/環境制約を報告する
3. statusを`In Progress`から`Review`へ変更する
4. `Completion`はcommit前のため`-`のままとし、review対象差分を提示する

### Completing a unit

依頼者のreview承認とcommit完了後にだけ`Review`から`Completed`へ変更します。
overviewと詳細の両方を更新し、`Completion`へfull commit hash、completion date、
必要なら短い互換性/残存リスクnoteを記録します。

実装commitにtracker更新を含めるか、直後の小さいdocumentation commitにするかは
reviewの明瞭さを優先します。ただしunit完了後にtrackerが古い状態のままにならないようにします。

### Changing the roadmap

- 既存R3 IDを別の目的へ再利用しない
- scope、priority、dependency、phase、acceptanceを変更した場合は理由をRoadmap change logへ記録する
- unitを取りやめる場合も削除せず、`Deferred`または`Superseded`にして理由と再評価条件/置換先を残す
- 新しい独立作業が必要なら次の未使用R3 IDを追加し、summaryの総数とstatus件数を更新する
- unitの分割/統合では元IDの履歴を残し、completion commitを実装commitの探索に使える状態にする

## Roadmap change log

Git履歴から分からないpriority、scope、順序、review gateの変更理由をここへ記録します。

| Date | Affected units | Change and rationale | Commit |
| --- | --- | --- | --- |
| 2026-09-05 | R3-028 | typed化後も実行失敗・判定エラーを不正解へ変換する表示が残るため、frontend限定の修正unitを追加。依頼者指定でreview前に一時使用したDoneは実装・検査完了、未commitを表し、承認・commit後はCompletedへ移行 | `eb9e458` |
| 2026-09-05 | R3-027 | R3-028追加後もrelease対象が古いID範囲で打ち切られないよう、依存関係の表記を自身以外の全release対象unitへ整合 | - |
| 2026-09-05 | R3-023 | 次unitの実装依頼に基づき、現行配置で本番image・依存・OS userを分離する範囲を確定。専用host/VMとDB role分離は運用・migration設計が別途必要なためSOJ-006・SOJ-011へ残し、frontendを含むCompose全体E2EはR3-024へ維持 | `aacda56` |
| 2026-09-05 | R3-029 | 依頼者の将来実施希望により、責務別package整理とfile単位COPY解消を独立unitとして追加。R3-026の不要資産削除とは分け、R3-023・R3-024の回帰基準を前提とする。今回のR3-023実装には含めない | `aacda56` |
| 2026-09-05 | R3-024 | 次unitの実装依頼に基づき、既存Composeの実経路・停止復帰・browser・全問題回帰を対象とした。独立reaperは権限境界と運用設計を伴うためSOJ-002へ維持し、R3-025のCI整備は含めない | `48a0670` |
| 2026-09-05 | R3-025 | 既存CIを維持して検査・候補生成・main限定provenanceを構成。実scanで検出した依存/image更新はSOJ-022へ記録し、既存検出を自動除外しない。GitHubのremote設定変更・署名実行・本番promotionは依頼者による反映後の確認とする | - |
| 2026-09-05 | SOJ-022 | 次の対策実装依頼に対し、CI停止の原因となるP1の依存是正を優先。アプリ依存・nginx更新と残存image課題はsecurity trackerで管理し、R3-029・R3-026の範囲は維持する | `cb044c7` |
| 2026-09-05 | SOJ-022 | アプリ依存是正に続きDB imageを独立単位で是正。公式PostgreSQL 15からOpenSSL・gosuだけを更新し、既存volume互換性とCIのscan対象一致を検証する。R3 package再配置・DB role分離は含めない | - |

## Tracker history

Git履歴と重複する細かな文言修正ではなく、計画の節目だけを記録します。

| Date | Change | Commit |
| --- | --- | --- |
| 2026-08-25 | Initial v3.0.0 refactoring roadmap recorded at baseline `991ef334f2785cce81a2e33206ec1f00f3487c9b` | - |
| 2026-08-26 | R3-001 implementation and planned tests completed; moved to `Review` | `74a1a74` |
| 2026-08-26 | R3-001 approved and recorded as `Completed` | `74a1a74` |
| 2026-08-26 | R3-002 implementation and planned tests completed; moved to `Review` | `6061ebc` |
| 2026-08-26 | R3-002 approved and recorded as `Completed` | `6061ebc` |
| 2026-08-26 | R3-003 implementation and planned tests completed; moved to `Review` | - |
| 2026-08-26 | R3-003 approved and recorded as `Completed` | `3843e37` |
| 2026-08-27 | R3-004 implementation and planned tests completed; moved to `Review` | - |
| 2026-08-27 | R3-004 approved and recorded as `Completed` | `9510c1f` |
| 2026-08-27 | R3-005 characterization and planned tests completed; moved to `Review` | - |
| 2026-08-28 | R3-005 approved and recorded as `Completed` | `79ca954` |
| 2026-08-30 | R3-006 schema, migration tooling, and planned tests completed; moved to `Review` | - |
| 2026-08-30 | R3-006 approved and recorded as `Completed` | `e710670` |
| 2026-08-30 | R3-007 all-problem migration and planned tests completed; moved to `Review` | - |
| 2026-08-30 | R3-007 approved and recorded as `Completed` | `4d25fa8` |
| 2026-08-31 | R3-012 sandbox lifecycle separation started | - |
| 2026-08-31 | R3-012 implementation and planned tests completed; moved to `Review` | - |
| 2026-08-31 | R3-012 approved and recorded as `Completed` | `370e5b8` |
| 2026-08-31 | R3-013 structured execution outcome implementation started | - |
| 2026-08-31 | R3-013 implementation and planned tests completed; moved to `Review` | - |
| 2026-09-01 | R3-013 approved and recorded as `Completed` | `97315a6` |
| 2026-09-01 | R3-014 privacy and retention gate decided; implementation started | - |
| 2026-09-01 | R3-014 implementation and planned tests completed; moved to `Review` | - |
| 2026-09-01 | R3-014 approved and recorded as `Completed` | `b7cb6f9` |
| 2026-09-01 | R3-015 implementation and planned tests completed; moved to `Review` | - |
| 2026-09-02 | R3-015 approved and recorded as `Completed` | `105ec70` |
| 2026-09-02 | R3-016 typed public API implementation and planned tests completed; moved to `Review` | - |
| 2026-09-02 | R3-016 approved and recorded as `Completed` | `074f450` |
| 2026-09-03 | R3-017 runner authentication, readiness, and revision checks completed; moved to `Review` | - |
| 2026-09-03 | R3-017 approved and recorded as `Completed` | `07545a5` |
| 2026-09-03 | R3-018 safe structured logging and request correlation completed; moved to `Review` | - |
| 2026-09-03 | R3-018 approved and recorded as `Completed` | `45d5482` |
| 2026-09-03 | R3-019 typed frontend API client completed; moved to `Review` | - |
| 2026-09-03 | R3-019 approved and recorded as `Completed` | `82a19be` |
| 2026-09-03 | R3-020 submission state and cancellation completed; moved to `Review` | - |
| 2026-09-03 | R3-020 approved and recorded as `Completed` | `bc6e60c` |
| 2026-09-04 | R3-021 frontend toolchain and browser CSP completed; moved to `Review` | - |
| 2026-09-04 | R3-021 approved and recorded as `Completed` | `872bacf` |
| 2026-09-04 | R3-022 runtime artifact pinning and mount hardening started | - |
| 2026-09-04 | R3-022 implementation and planned tests completed; moved to `Review` | - |
| 2026-09-04 | R3-022 approved and recorded as `Completed` | `eff33ca` |
| 2026-09-05 | R3-028 approved and recorded as `Completed` | `eb9e458` |
| 2026-09-05 | R3-023 split runtime images, non-root execution, and planned tests completed; moved to `Review` | - |
| 2026-09-05 | R3-023 approved and recorded as `Completed`; R3-029 remains `Planned` | `aacda56` |
| 2026-09-05 | R3-024 approved and recorded as `Completed` | `48a0670` |
| 2026-09-05 | R3-025 approved and recorded as `Completed`; vulnerability remediation and hosted verification remain tracked separately | `7b779b3` |
