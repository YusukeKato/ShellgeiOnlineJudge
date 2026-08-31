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
- Total refactoring units: 27
- Ready: 0
- Planned: 15
- Pending (`Ready` + `Planned`): 15
- In Progress: 0
- Review: 0
- Completed: 12
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
| R3-013 | P0 | Planned | C | Capture structured execution outcomes | R3-012 | - |
| R3-014 | P1 | Planned | C | Introduce ExecutionLogRepo and database migrations | R3-003, R3-009 | - |
| R3-015 | P0 | Planned | C | Introduce SubmitSolutionService | R3-008, R3-010, R3-011, R3-014 | - |
| R3-016 | P1 | Planned | C | Expose typed public API v3 contract | R3-015 | - |
| R3-017 | P1 | Planned | C | Harden runner authentication, readiness, and revision checks | R3-008, R3-009 | - |
| R3-018 | P2 | Planned | C | Add safe structured logging and request correlation | R3-015 | - |
| R3-019 | P1 | Planned | D | Introduce typed frontend API client | R3-005, R3-016 | - |
| R3-020 | P1 | Planned | D | Model frontend submission state and cancellation safely | R3-019 | - |
| R3-021 | P2 | Planned | D | Consolidate frontend toolchain after behavior coverage | R3-020 | - |
| R3-022 | P1 | Planned | E | Pin runtime artifacts and harden mounts and configuration | R3-013 | - |
| R3-023 | P1 | Planned | E | Split production backend and runner images | R3-017, R3-022 | - |
| R3-024 | P1 | Planned | E | Add full rootless Compose E2E regression | R3-016, R3-017, R3-023 | - |
| R3-025 | P2 | Planned | E | Harden CI and software supply-chain checks | R3-004, R3-022, R3-024 | - |
| R3-026 | P3 | Planned | F | Remove obsolete code, assets, scripts, and dependencies | replacement units | - |
| R3-027 | P3 | Planned | F | Establish canonical v3.0.0 version and release documentation | R3-001--R3-026 release scope | - |

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
- Completion: commit `79ca954` / date 2026-08-28 / legacy problem corpus, judge behavior, frontend API/display behavior, and known defects characterized

## Phase B — Domain / Problem / Judge

### R3-006: Introduce v3 problem schema and migration tooling

- Priority / Status: P0 / `Completed`
- Goal: schema version、execution input/fixture、judge type、exit/stderr policy、artifactを明示する型付きproblem schemaを導入する
- Main files/components: problem domain model、schema validator、migration tool、`problems/README.md`、代表problem 3件程度
- Dependencies: R3-005
- Risk: Medium。既存problemの暗黙的な意味を誤って変換しないこと
- Expected tests: valid/invalid schema、duplicate/extra/missing field、path/size/image制約、pilot problem回帰
- Size: M
- Completion: commit `e710670` / date 2026-08-30 / typed schema v3, strict YAML validation, deterministic legacy migration, and three pilot problems introduced without changing the production read path

### R3-007: Migrate all problem definitions to schema v3

- Priority / Status: P0 / `Completed`
- Goal: 全92問をv3 schemaへ機械的に移行し、text/image judge、fixture、入力を明示する
- Main files/components: `problems/v3/*.yaml`、fixture、problem migration検査、全問題Docker回帰
- Dependencies: R3-006、reference solution公開方針のreview gate
- Risk: Medium。差分量が大きく、問題文や正解データの意図しない変更を見落としやすい
- Expected tests: 全problem schema検証、移行前後semantic manifest、代表実行、全問題回帰
- Size: L
- Completion: commit `4d25fa8` / date 2026-08-30 / all 92 problems migrated deterministically with legacy semantic equality and rootless Docker answer regression verified

### R3-008: Introduce immutable ProblemRepo and manifest digest

- Priority / Status: P0 / `Completed`
- Goal: YAML/imageの重複読込を一元化し、startup時に検証済みのimmutableな`ProblemDefinition`とproblem data revisionを提供する
- Main files/components: problem catalog/repository、backend startup、runner startup、problem API/judge caller
- Dependencies: R3-007
- Risk: Medium。cache lifetime、startup failure、backend/runner間のdata不一致を正しく扱う必要がある
- Expected tests: startup validation、immutable lookup、missing/corrupt data、manifest digest一致/不一致
- Size: M
- Completion: commit `6360c34` / date 2026-08-30 / startup-validated immutable problem repository, canonical manifest revision, and v3 production read path introduced

### R3-009: Introduce typed runner execution protocol

- Priority / Status: P0 / `Completed`
- Goal: runner応答を`[output, image]`やmagic stringからtyped `ExecutionResult`へ移行できる内部protocolを定義する
- Main files/components: runner request/response model、`RunnerGateway`、runner endpoint、protocol test
- Dependencies: R3-005
- Risk: Medium。public backendとrunnerを同時に移行し、size limitと認証を維持する必要がある
- Expected tests: serialization、unknown field/version、response size、timeout/unavailable、互換移行境界
- Size: M
- Completion: commit `62dadf6` / date 2026-08-30 / versioned strict request/response models, typed ExecutionResult, and RunnerGateway introduced without changing the public API

### R3-010: Extract pure text judge and typed JudgeResult

- Priority / Status: P0 / `Completed`
- Goal: file I/Oをjudgeから除き、token置換/`NULL`衝突をなくして、明示的なnewline・space・stderr・exit policyでtext verdictを返す
- Main files/components: judge domain model、pure text judge、problem judge specification、judge test corpus
- Dependencies: R3-006、R3-009
- Risk: High。現在の誤ったacceptを含む判定結果が変わるため、意図したbreaking changeの確認が必要
- Expected tests: whitespace truth table、token literal、empty/`NULL`、non-zero exit、stderr、timeout/truncation、全text problem回帰
- Size: M
- Completion: commit `91fdbad` / date 2026-08-30 / pure typed text judge, collision-free comparison, explicit execution policies, and legacy public code mapping introduced

### R3-011: Separate and correct image judging

- Priority / Status: P0 / `Completed`
- Goal: text問題から暗黙の画像判定を除き、artifact MIME/pathと画像比較方式をschemaで明示し、先頭byte除外による誤判定をなくす
- Main files/components: image judge、artifact model、problem schema、runner capture、frontend contract
- Dependencies: R3-007、R3-009、image comparison strategyのreview gate
- Risk: High。既存5画像問題、JPEG/GIF、表示MIME、正規化方針へ影響する
- Expected tests: exact/corrupt/header-only差分、JPEG/GIF MIME、missing/multiple artifact、5画像問題回帰
- Size: M--L
- Decision: JPEG encoder metadataの差を許容しつつ表示内容を厳密に比較するため、形式検証後の寸法・frame数・RGBA画素完全一致を採用。schema指定pathだけを取得し、複数候補から暗黙選択しない
- Completion: commit `7947640` / date 2026-08-30 / schema-selected typed artifacts, strict JPEG/GIF validation, exact-pixel judging, MIME-aware public response and frontend display introduced

## Phase C — Execution / Application / API

### R3-012: Separate sandbox preparation, execution, capture, and cleanup

- Priority / Status: P1 / `Completed`
- Goal: archive準備、container割当、exec、watchdog、出力capture、破棄を小さい責務へ分け、raceとresource leakを検証可能にする
- Main files/components: execution archive、`SandboxExecutor`、`ContainerManager`、runner service
- Dependencies: R3-009
- Risk: High。Docker lifecycleとsecurity invariantを変更するため、timeout/例外時も必ずfresh containerを破棄する必要がある
- Expected tests: fake Docker unit、create/start/exec/capture/cleanup failure、concurrency、Docker lifecycle integration
- Size: M
- Completion: commit `370e5b8` / date 2026-08-31 / `SandboxPreparer`、
  `SandboxOutputCapturer`、`ExecutionWatchdog`、`SandboxCleanup`、
  `SandboxExecutor`へ責務を分離し、timeout側killの完了後に停止済み返却する同期を追加。
  fake Docker failure unit、Python 3.14の非Docker 418件、rootless Docker integration
  7件が成功。full problem regression 1件は明示flag未指定のためskip

### R3-013: Capture structured execution outcomes

- Priority / Status: P0 / `Planned`
- Goal: exit code、stdout、stderr、timeout、truncation、duration、binary artifactを別々にcaptureして`ExecutionResult`を完成させる
- Main files/components: Docker exec adapter、capture limits、artifact reader、execution model
- Dependencies: R3-012
- Risk: High。memory/output limit、background process、binary data、cleanup順序の回帰を避ける
- Expected tests: exit/stderr分離、invalid UTF-8、NUL、byte/character limit、timeout、background writer、Docker/full regression
- Size: M--L
- Completion: commit `-` / date `-` / note `-`

### R3-014: Introduce ExecutionLogRepo and database migrations

- Priority / Status: P1 / `Planned`
- Goal: persistenceをapplication/APIから分離し、typed resultを安全に保存できるschema、migration、transaction、retention境界を導入する
- Main files/components: DB model、`ExecutionLogRepo`、migration、retention、database test
- Dependencies: R3-003、R3-009、execution log retention/privacyのreview gate
- Risk: Medium--High。既存volume/data migrationとrollback、保持policyに影響する
- Expected tests: forward/rollback migration、transaction failure、retention、real PostgreSQL integration
- Size: M
- Completion: commit `-` / date `-` / note `-`

### R3-015: Introduce SubmitSolutionService

- Priority / Status: P0 / `Planned`
- Goal: problem取得、runner実行、判定、保存をtyped use caseへ集約し、HTTP handlerをtransport mappingだけにする
- Main files/components: application service、domain result、ProblemRepo/RunnerGateway/Judge/ExecutionLogRepo ports、API handler
- Dependencies: R3-008、R3-010、R3-011、R3-014
- Risk: Medium。error mappingと保存順序を維持しつつ、infrastructure failureをwrong answerから分離する
- Expected tests: fake portsによるsuccess/not-found/busy/timeout/judge/persistence failure、call ordering
- Size: M
- Completion: commit `-` / date `-` / note `-`

### R3-016: Expose typed public API v3 contract

- Priority / Status: P1 / `Planned`
- Goal: request/response DTO、typed verdict、execution failure、artifact MIME、HTTP statusを明文化しfrontendとのcontractを固定する
- Main files/components: FastAPI route/model、OpenAPI、HTTP mapper、API documentation
- Dependencies: R3-015
- Risk: Medium。public contractのbreaking changeとfrontend移行を同期する必要がある
- Expected tests: ASGI 200/404/422/429/503、OpenAPI schema、response size/cache/security header
- Size: M
- Completion: commit `-` / date `-` / note `-`

### R3-017: Harden runner authentication, readiness, and revision checks

- Priority / Status: P1 / `Planned`
- Goal: request body parse前にrunner認証を行い、pool劣化をreadinessへ反映し、protocol/problem revision不一致をfail-closedにする
- Main files/components: runner middleware/endpoint、health/readiness、RunnerGateway、Compose healthcheck
- Dependencies: R3-008、R3-009
- Risk: Medium。ASGI request処理順、起動中のreadiness、rolling update互換性へ影響する
- Expected tests: unauthorized large body、body limit、degraded pool、protocol/data digest mismatch、restart behavior
- Size: M
- Completion: commit `-` / date `-` / note `-`

### R3-018: Add safe structured logging and request correlation

- Priority / Status: P2 / `Planned`
- Goal: public APIからrunner/DBまでrequest IDと安全なstatus/durationを追跡し、command、output、secretを不用意にlogしない
- Main files/components: logging configuration、middleware、application/runner events、運用文書
- Dependencies: R3-015
- Risk: Low--Medium。sensitive data漏えいとlog cardinality増加を防ぐ
- Expected tests: correlation propagation、redaction、no raw command/output/secret、failure event coverage
- Size: S--M
- Completion: commit `-` / date `-` / note `-`

## Phase D — Frontend

### R3-019: Introduce typed frontend API client

- Priority / Status: P1 / `Planned`
- Goal: raw `fetch`、tuple、`any`、magic verdict判定をtyped clientと明示的なDTO mappingへ置き換える
- Main files/components: frontend API client/types、problem/result functions、component props、API mock
- Dependencies: R3-005、R3-016
- Risk: Medium。表示上の互換性とAPI移行期間を管理する必要がある
- Expected tests: typed success/error fixtures、unknown verdict、artifact MIME、problem selection、lint/type/build
- Size: M
- Completion: commit `-` / date `-` / note `-`

### R3-020: Model frontend submission state and cancellation safely

- Priority / Status: P1 / `Planned`
- Goal: submission stateをdiscriminated unionで表し、`AbortController`、duplicate防止、selection/response race、timeout表示を正しく扱う
- Main files/components: React state/hooks、submit/result components、API cancellation、frontend test
- Dependencies: R3-019
- Risk: Medium。非同期UI behaviorと既存操作感へ影響する
- Expected tests: timeout/abort、double submit、out-of-order response、selection race、latest request wins、JPEG/GIF表示
- Size: M
- Completion: commit `-` / date `-` / note `-`

### R3-021: Consolidate frontend toolchain after behavior coverage

- Priority / Status: P2 / `Planned`
- Goal: behavior testを先に確保した後、維持可能なbuild/test/lint/typecheck構成へ統合し、必要ならdeprecatedなCRAから移行する
- Main files/components: frontend package/build config、test setup、Dockerfile、frontend documentation
- Dependencies: R3-020、Analytics/Google Fonts/CSPのreview gate
- Risk: Medium。build artifact、environment variable、nginx配信、browser behaviorが変わり得る
- Expected tests: format、lint、typecheck、unit/component test、production build、nginx smoke
- Size: M
- Completion: commit `-` / date `-` / note `-`

## Phase E — Runtime / Supply Chain / E2E

### R3-022: Pin runtime artifacts and harden mounts and configuration

- Priority / Status: P1 / `Planned`
- Goal: imageをdigestで固定し、sandboxの予期しないmount/volumeを拒否し、nginx設定等のwritable bind mountをなくす
- Main files/components: Compose、Dockerfiles、ContainerManager validation、nginx configuration、security documentation
- Dependencies: R3-013
- Risk: High。image更新手順、rootless runtime、sandbox startupを変更する
- Expected tests: Compose静的test、image inspect、mount/volume rejection、rootless Docker baseline/full regression
- Size: M
- Completion: commit `-` / date `-` / note `-`

### R3-023: Split production backend and runner images

- Priority / Status: P1 / `Planned`
- Goal: backendとrunnerのruntime image/dependencyを分け、non-rootとleast privilegeを適用し、productionへtest/development dependencyを持ち込まない
- Main files/components: backend/runner Dockerfiles、dependency groups、Compose、DB role/config、deployment docs
- Dependencies: R3-017、R3-022、runner専用host/VM判断のreview gate
- Risk: High。Docker socket access、UID/GID、rootless運用、build/release artifactへ影響する
- Expected tests: reproducible image build、user/dependency inspection、runner socket access、backend socket非保持、Compose integration
- Size: M--L
- Completion: commit `-` / date `-` / note `-`

### R3-024: Add full rootless Compose E2E regression

- Priority / Status: P1 / `Planned`
- Goal: frontend/nginxからbackend、runner、rootless Docker、PostgreSQLまでの実経路を自動検証する
- Main files/components: Compose E2E fixture/test、rootless wrapper、integration documentation、test data
- Dependencies: R3-016、R3-017、R3-023、runner外reaper判断のreview gate
- Risk: High。専用rootless Docker環境と安全なcleanupが必要で、通常hostで破壊的耐性試験を行わない
- Expected tests: success/wrong/execution failure、auth/revision mismatch、restart/recovery、DB persistence、frontend proxy、full problem regression
- Size: M
- Completion: commit `-` / date `-` / note `-`

### R3-025: Harden CI and software supply-chain checks

- Priority / Status: P2 / `Planned`
- Goal: CI token権限、timeout、supported runtime matrix、dependency/image/secret scan、SBOM、artifact provenanceを段階的に導入する
- Main files/components: `.github/workflows/`、dependency update policy、image build/promotion、security documentation
- Dependencies: R3-004、R3-022、R3-024
- Risk: Medium。external scannerのavailability、false positive、artifact release flowを管理する必要がある
- Expected tests: workflow validation、least-permission review、scanner fixtures、SBOM/provenance generation、required checks
- Size: M
- Completion: commit `-` / date `-` / note `-`

## Phase F — Cleanup / Release

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
- Dependencies: v3 release scopeに含めるR3-001--R3-026が`Completed`、または未完了unitのdefer判断が承認済み
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
| runnerを専用hostまたは使い捨てVMへ分離するか | Open | R3-023の最終設計、またはv3 release scope確定 | - | - |
| runner process外の独立reaperを導入するか | Open | R3-024のrecovery acceptance確定 | - | - |
| Analytics / Google Fontsを維持するか、CSPをどう設定するか | Open | R3-021 | - | - |
| reference solutionをpublic frontend/API artifactに含めるか | Decided | R3-007 | 現行どおりpublic problem detail APIで公開する | 既存APIは`answer`をすでに公開しているためR3-016以前の互換性を維持し、v3では`reference_solution`として保持する。2026-08-30決定、commit `4d25fa8` |
| execution logの利用目的、保持期間、privacy、backup方針 | Open | R3-014 | - | - |
| imageをbyte exact、canonicalized、pixel比較のどれで判定するか | Open | R3-011 | - | - |

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
| Frontend contract | raw tuple/`any`/magic verdictに依存し、infrastructure errorをwrong answerとして表示し得る | R3-019、R3-020 |
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
| - | - | No roadmap changes after initial recording | - |

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
