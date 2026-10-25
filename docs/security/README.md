# セキュリティ課題と対応状況

## 目次

- [目的](#目的)
- [照合対象と確認範囲](#current-baseline)
- [現在の対応状況](#current-security-status)
- [未解決課題](#issue-tracker)
- [SOJ-022の確認時点と失効policy](#soj-022の現在の停止対象)
- [SOJ-002の残存課題](#open-issue-details)
- [保留理由](#deferred-issues)
- [本番環境で別途必要な確認](#production-only-verification)
- [テストの対応表と未確認範囲](#test-coverage)
- [次の作業](#recommended-next-steps)
- [作業再開手順](#作業再開手順)

## 目的

この文書は、現在のセキュリティ課題、対応状況、優先順位を追跡する正本です。
後日、開発者や新しいCodexセッションが実装を再開するときの入口として使用します。

この文書は、security modelやsandbox仕様そのものの正本ではありません。
現在の仕様は[SECURITY.md](../../SECURITY.md)、
本番構成と運用手順は[本番運用](../PRODUCTION.md)を参照してください。
初回監査時の根拠と検証結果は、
[2026-08-23監査記録](./audit-2026-08-23.md)に保存しています。

この文書より、現在のコード、設定、テスト、実環境を優先します。
再開時は各課題が現在も成立するか、必ず再検証してください。

## Current baseline

この節は記録済みの照合対象を示します。以降の限定確認で全体監査のbaselineを更新したとは扱いません。
2026-10-17のDB保存受付の確認は[Current security status](#current-security-status)、
10月11日・7日の依存更新の範囲は[SOJ-022の確認時点](#soj-022の現在の停止対象)を参照してください。
本番host・公開proxy・WAF・実際のDB・監視基盤は、別途確認が必要です。

- 限定照合日: 2026-10-07
- branch: `integration/security-and-three-problems-20261007`
- 確認対象commit: `e52b19b780fef0af5a5676c4613707e6127eae7e`
- commit subject: `Merge runtime security fixes and three new problems`
- 確認時のworktree: clean
- 対象: SOJ-022の限定更新と問題62・63・PRACTICE-od-01の統合差分、ローカル検証、同一commitのGitHub CI
- 当該照合の変更: Python・対象OS library・source-map-jsの更新と3問追加を統合。詳細は[統合候補の検証結果](./dependency-remediation-history.md#2026-10-07の統合候補とgithub-ci)を参照
- 対象外: 未解決課題全体の再監査、本番host、外側reverse proxy、WAF、実際の本番DBと監視基盤

全体監査の過去baselineは2026-09-06の`34a9041`です。この限定確認によって、他の未解決課題を解決済みとは扱いません。

baseline以降に変更がある場合は、先に差分を確認してください。

```sh
git status --short
git log -1 --oneline
git diff e52b19b780fef0af5a5676c4613707e6127eae7e
```

## Current security status

- frontendのBrotli runtime libraryと、開発検査用のZod・Undiciをvendor修正版へ限定更新しています。
  固定値は[frontend Dockerfile](../../frontend/Dockerfile)と[lock](../../frontend/yarn.lock)を正本とします。
  収録packageから公開request経由の悪用成立までは確認していません。
  対象経路・検証範囲・残存事項は
  [2026-10-25の限定是正記録](./dependency-remediation-history.md#2026-10-25のbrotlizodundici更新)を参照してください。
  TLS・CA、API・sandbox制限、scan停止条件は維持します。

- frontendの不要なcurl/libcurlを通常のpackage依存解決で削除し、
  CVE-2026-92392の対象client/libraryを実行用imageへ残さない構成にしています。
  nginx本体・module・起動script、CA、外部端末向けcurl例は維持します。
  対象と検証範囲は[2026-10-22の限定是正記録](./dependency-remediation-history.md#2026-10-22のfrontend-curllibcurl削除)を参照してください。
  ローカル候補の検証と本番反映の完了を区別し、CI・配備は対象commitで別途確認します。

- eMudhra中間CA鍵漏えいへの対応として、OS CA、runnerのcertifi、Pythonのpip/ensurepip、
  Node.js・Goのbuild環境を更新します。
  現行version・取得hashは[lock](../../poetry.lock)を正本とします。
  [2026-10-21の限定是正記録](./dependency-remediation-history.md#2026-10-21のcertifi信頼ストア更新)に
  公式情報・到達条件・検証範囲を記載しています。TLS検証とscan停止条件は維持します。
  [CA検査](../CI.md#ca信頼ストアの検査)で漏えいCA経由の12 chainの拒否と正常chainの許可を必須にします。
  その他の固定値は各Dockerfile・`ci/bootstrap_pip.py`を正本とします。
  本番hostの更新は運用者の担当であり、アプリimageの配備とは別に確認します。
- frontendのnginx baseとX11/XPM libraryをvendor修正版へ更新しています。
  共有TLS session cacheを使うため、nginxのTLS session ticketの指摘も対象です。
  X11/XPMはimageへ収録されていますが、通常のHTTP処理からの到達経路は確認していません。
  固定versionは[frontend Dockerfile](../../frontend/Dockerfile)を正本とし、実imageのversion検査と
  最新DBによるscanを併用します。対象・検証時点・残存指摘は
  [2026-10-19の是正記録](./dependency-remediation-history.md#2026-10-19のfrontend-nginxx11xpm更新)を参照してください。
  TLS検証、API・sandbox制限、scanの停止条件は維持します。
- backend用Pillowを13.0.0へ更新し、12.3.0までが対象となる画像decoderの公開指摘に対応します。
  現在のversionは[依存定義](../../pyproject.toml)と[lock](../../poetry.lock)を正本とします。
  [GIFコメント解析の指摘](https://github.com/python-pillow/Pillow/security/advisories/GHSA-74r2-7ff9-mjj2)は、
  sandboxから返るGIFをbackendが開く処理へ到達します。byte上限は維持しますが、画素上限だけでは
  コメント解析のCPU負荷を制御できません。750,000 bytes以内での実際の可用性影響は未計測です。
  [13.0.0の互換性変更](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)に対し、
  画像判定・GIFの原本bytes、frame・delay・loop保持、破損入力・上限検査を回帰対象とします。
  sandboxとrunnerの制限、判定方法、public APIの仕様は維持します。
- DB遅延時の実行ログ滞留に対し、保存入口の非待機受付制限を実装しています
  （2026-10-17検証）。保証範囲は
  [実行ログの制約](../../SECURITY.md#実行ログとdockerログ)を参照してください。
  rootlessの使い捨て環境で実proxy・Uvicorn・runner・PostgreSQLを使い、通常DBの16提出は
  全件保存、25秒のDBロック中の18切断提出では未完了保存最大4件・観測待ちキュー0件・
  満杯拒否3件、解除後の保存復帰を確認しました。DB遅延は管理側の故障注入であり、
  外部利用者がDB遅延自体を作れるとの確認ではありません。専用資源は回収済みです。
  継続回帰は`test_execution_log_admission.py`と`test_postgres_retention.py`で行います。
- SOJ-022の限定更新と3問追加を統合した`e52b19b`は、GitHubのFastAPI・React・Supply Chain CIが成功しました。
  [統合候補の検証結果](./dependency-remediation-history.md#2026-10-07の統合候補とgithub-ci)を参照してください。
  当該候補のsourceと全5製品では停止対象・例外・リスク受容0を確認しましたが、runtimeの非ブロック指摘は残ります。
  Windows mypyのOSポリシー拒否自体は未解決です。本番の状態は、mainの同一SHAのCI・署名・配備結果と照合します。
- インターネット公開には、外側proxyまたはWAFの
  実client単位の受付制御を別途確認する必要があります。
- runner異常終了後のsandboxは再起動時に回収します。
  Docker daemon単独の有効期限はないため、SOJ-002を部分解決として追跡します。
- read-only root、tmpfs容量・inode、CPU、memory、swap、PID、
  capability、network、IPC、timeout等の主要sandbox制限は実装され、
  現在のrootless開発環境で実効値を確認しています。
- backendからDocker socketを外し、認証付き内部runnerへ分離した設計は有効です。
  ただし、runnerと他serviceは同じrootless daemonとVMを共有しています。
- R3-023の非root image分離に加え、SOJ-011でDB管理処理を独立serviceへ分離しました。
  通常roleの最小権限とbackend起動時の読み取り検証を実装済みです（`4eec07b`でcommit済み、本番移行は未実施）。
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
  - 概要: 起動時回収・Docker失敗時の追跡に加え、独立したホスト監視CLIを実装（`b422b01`でcommit済み）。
    daemon単独のsandbox有効期限はない
  - 関連: `backend/soj_runner/container_manager.py`、`backend/soj_tools/sandbox_health.py`
  - 次: 本番監視への定期実行・alert接続と、独立した期限強制の要否を判断
- `SOJ-006` — Medium / P1 / Deferred
  - 概要: runner侵害時の影響が同一daemon上のDB、frontend、TLS鍵へ及ぶ
  - 関連: `docker-compose.yml`
  - 次: runner専用hostまたは使い捨てVMへ分離
- `SOJ-012` — Medium / P2 / Partially resolved
  - 概要: DB行数・Docker service logは制限したが、host I/O、
    DB volume、image cacheにquotaがない
  - 関連: `docker-compose.yml`、`backend/soj_backend/execution_log_retention.py`
  - 次: 専用filesystem、I/O制御、quota、監視を本番設計へ追加
- `SOJ-019` — Medium / P2 / Partially resolved
  - 概要: CI権限・timeout・Action SHA、secret/依存/image scan、SBOMとmain限定provenanceを構成した。
    同じmain SHAの全CI成功・署名検証後のSSH promotionも構成した。
    統合候補のGitHub CIは確認済み。本番の署名・配備、required checks・review保護は対象main SHAでの確認が必要で、第三者供給元署名は未導入
  - 関連: `.github/workflows/`、[CI文書](../CI.md)
  - 次: 対象main SHAのCIとOIDC署名、required checks・workflow変更のreview保護を確認する。設定変更は別途レビューする。
    bootstrapの間接依存・第三者imageの供給元検証を整備し、[SSH自動更新](../AUTODEPLOY.md)の実接続と復旧を確認する
- `SOJ-022` — High/Critical（scanner分類） / P1 / Partially resolved
  - 概要: Python 3.12.15 / Expat 2.8.5と対象OS libraryへ更新し、統合候補のCIで例外・受容なしの停止対象0を確認。非ブロック指摘は残る
  - 関連: `pyproject.toml`、`poetry.lock`、`frontend/yarn.lock`、`frontend/Dockerfile`、`deploy/postgres/Dockerfile`、`ci/python-runtime-exceptions.json`、`deploy/sandbox/`、runtime image
  - 確認: [是正記録](#soj-022依存imageの是正記録)に変更範囲、検出比較、未解決範囲を記載
  - 次: [現在の検出と検証結果](#soj-022の現在の停止対象)を基に残存指摘と公式修正版を再評価し、mainの同一SHAのCI・署名・本番反映を確認する。
    [失効した旧policy](#soj-022の一時許容と撤去条件)は非適用の監査記録として残る。policy・専用処理の撤去は未実施で、別の変更としてレビューする
- `SOJ-021` — Low / P3 / Partially resolved
  - 概要: command/output保持の目的・最小field・backup方針は確定したが、
    非公開脆弱性報告手順は未整備
  - 関連: `backend/soj_backend/models/execution_log.py`、
    `backend/soj_backend/execution_log_repository.py`、`SECURITY.md`
  - 次: security contactと非公開報告手順を決定

現在の未解決trackerは次の内訳です。

- Open: 0件
- Partially resolved: 5件
- Deferred: 1件
- Severity: High/Critical 1件、Medium 4件、Low 1件

SOJ-020は下記の実装・検証により`Resolved`としました。未解決は上記6件です。

## SOJ-022の現在の停止対象

この文書に記録されたscan・修正確認は、次の時点と対象に限ります。最新scanの再実行結果ではありません。

| 記録時点 | 対象と確認範囲 | 残る確認 |
| --- | --- | --- |
| 2026-10-11 | gosu・textimgのGo 1.26.9への更新とrootless統合。個別ID・結果は[Go更新記録](./dependency-remediation-history.md#2026-10-11のgo標準library更新) | 記録時点では同一headの全CI成功までmerge・配備を停止 |
| 2026-10-07 | 統合候補`e52b19b`のsource・5製品で停止対象・例外・リスク受容0。非ブロック指摘は残る。[GitHub CI確認記録](./dependency-remediation-history.md#2026-10-07の統合候補とgithub-ci) | mainの同一SHAのCI・署名・本番配備とは別の結果 |

残存指摘と公式修正版を再評価し、対象main SHAのCI・署名・配備結果を別途照合してください。
停止対象0を全脆弱性0や安全性の保証として扱いません。
過去の検出比較・検証件数・未確認範囲は[依存・image是正の検証記録](./dependency-remediation-history.md)に保持しています。

## SOJ-022の一時許容と撤去条件

旧リスク受容policyは2026-10-04、旧Python誤検出例外は2026-10-05に失効し、非適用の監査記録として残っています。
統合候補`e52b19b`の記録では適用0です。policy・専用処理の撤去は未実施で、別の変更としてレビューします。
[当時の承認条件・影響評価・撤去条件](./dependency-remediation-history.md#soj-022の一時許容と撤去条件)を保存しています。
現行の期限・実装照合・失効時の挙動は[CI文書](../CI.md#未修正python脆弱性の一時的なリスク受容)を参照してください。
期限延長・対象拡張を、この履歴を根拠に行わないでください。

## SOJ-022：依存・imageの是正記録

過去の依存・DB・Python・独自sandboxの是正と検証結果は、
[依存・image是正の記録](./dependency-remediation-history.md#soj-022依存imageの是正記録)へ移しました。
当時の結果を現在のscan・本番確認として扱いません。

## Resolved issues

解決済み課題の一覧、commit、testとSOJ-011・SOJ-020の詳細は
[解決済み課題と部分対応の検証記録](./resolved-issues.md#resolved-issues)へ移しました。
現在の残存経路は[未解決課題](#open--partially-resolved--deferred)で管理します。
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
- rootless daemonを読み取るホスト監視CLI。runner状態とowner単位のsandbox残存・台数異常・instance混在を検出

不足と次の対応:

- ホスト監視CLIをproductionの定期監視・alertへ接続する（repository上の実装・検証のみ完了）
- 1 ownerにつきrunnerを1 instanceに限定する
- runnerとは独立したreaperによる期限強制が必要か運用要件を決定する
- 独立したreaperを追加する場合は、Docker socket権限の増加と分離方法を先に評価する

想定変更範囲:

- production監視・alert設定
- 必要と判断した場合のみ、runnerと独立した回収component

[2026-09-05の実装・検証記録](./resolved-issues.md#soj-002-ホスト監視cliの部分対応)を参照してください。

残存リスクを踏まえ、SOJ-002はMedium、P1、Partially resolvedとします。

## Deferred issues

### Architecture変更が必要

- SOJ-006は、runnerを専用hostまたは使い捨てVMへ移す必要があります。
  現在の内部HTTPは平文・固定URLであり、そのまま別hostへ公開してはいけません。

### Product方針が必要

- SOJ-021の非公開脆弱性報告窓口は、運用判断が必要です。

### CI・運用基盤が必要

- SOJ-019は、構成したCIとSSH promotionの実運用確認、review保護、第三者供給元検証が必要です。

Deferredは不要という意味ではありません。
必要な前提が整った時点でseverityとpriorityを再評価してください。

## Production-only verification

### 外側reverse proxy、TLS、client IP

- Repository guarantees:
  - Compose frontendは既定で`127.0.0.1:8443`だけに公開します。
  - 内部nginxはTLS 1.2/1.3、body・connection・proxy timeoutを設定します。
  - frontendは第三者script・外部fontを読み込まず、CSPで同一originへ制限します。
- Development environment verified:
  - repositoryのnginx設定testとlocal smoke testがあります。
  - rootless Docker上の実nginxで、CSP、Vite asset配信、第三者script不在を確認しています。
- Production verification required:
  - 公開443のTLS設定、証明書更新、HSTS、Host allowlist
  - upstream証明書検証、実client単位rate/connection limit、XFF trust
  - client IPを揮発性の受付制御だけに使用し、proxy・WAF・分析基盤へ
    raw値やhashを保存しないこと

### rootless Docker、kernel、runtime isolation

- Repository guarantees:
  - wrapperはlocal Unix socket以外とrootful daemonを拒否します。
  - Composeはrunnerの接続先をUnix socketへ固定し、runnerはrootless・cgroup条件と
    sandboxの制限実効値を検査します。
  - runner単体には接続先schemeを拒否する検査はなく、Compose外でもlocal rootless
    Unix socketを明示する運用が必要です。
- Development environment verified:
  - 直近のDocker統合testでrootless・cgroup v2・systemd、resource制限と隔離設定を確認。
    検証内容は[Docker統合テスト](../../backend/tests/integration/README.md)を参照します。
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
  - R3-025でGit履歴と現在の作業treeをGitleaksでscanし、検出なし。
    対象commitと検証範囲は[R3-025の検証記録](../refactoring/README.md#r3-025-harden-ci-and-software-supply-chain-checks)を参照。
    GitHub上での継続実行は反映後に確認する。
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
  - archive準備、exec、artifact取得、cleanupの失敗、timeout、出力上限、
    stdout/stderr・終了code分離、invalid UTF-8、NUL、文字数上限、所要時間、
    実行slot、kill完了待ち、background cleanup
- `backend/tests/test_runner_boundary.py`
  - secret、version付き固定schema、response上限、backend/runner分離、
    problem revision・request ID不一致の拒否
- `backend/tests/test_runner_http_security.py`
  - body読込前の認証、認証後body上限、HTTP framing
- `backend/tests/test_public_api_v3.py`、`test_http_boundary.py`
  - v3 DTO・HTTP status、内部error非公開、Host・slash・security header
- `backend/tests/test_database_migrations.py`、`test_execution_log_retention.py`
  - migration、retention、NUL、commit失敗時rollback、非同期保存・保存失敗時の応答
- `backend/tests/test_runner_protocol.py`
  - version 3 request/response JSON往復、未知version・field、構造化resultの
    status整合性・不変性・合計上限
- `backend/tests/test_text_judge.py`
  - text空白規則、literal衝突、終了code・stderr policy、timeout、切り詰め
- `backend/tests/test_image_judge.py`
  - JPEG/GIF、欠損・破損・path・MIME、全画素比較、旧先頭除外の回帰
- `backend/tests/test_problem_repository.py`
  - 起動時schema・画像・manifest検証、不変lookup、revision再計算
- `backend/tests/test_nginx_config.py`
  - nginx directiveの静的確認
- `backend/tests/integration/test_nginx_admission.py`
  - 実nginxで、非実行requestと正常requestが
    共有のsandbox開始枠を消費しないこと
- `backend/tests/integration/test_docker_executor.py`
  - 実containerの起動時回収、filesystem、resource、logging、
    isolation、stdout/stderr・終了code、timeout、画像、状態分離
- `backend/tests/integration/test_postgres_retention.py`
  - 実PostgreSQLのmigration・transactional DDL rollback、期間・件数制限、
    NUL保存、lock timeoutとrollback後の再保存
- `backend/tests/integration/test_full_problem_regression.py`
  - manifestに登録された全問題の正解commandとjudge互換性
- `backend/tests/integration/test_runtime_images.py`
  - build済み本番imageの非root・依存境界・socket group、内部network上の実行・判定・DB保存
- `backend/tests/integration/test_compose_e2e.py`
  - 実ComposeのTLS nginx・提出・DB保存、認証/revision拒否、DB/runner停止復帰、browser操作、全問題回帰
- `backend/tests/test_ci_policy.py`、`test_supply_chain.py`と`ci/`
  - workflow権限境界、toolの改変・symlink拒否、脆弱性gate、実scannerの検出・異常終了
- `frontend/src/legacy_behavior.test.jsx`、`playground.test.jsx`
  - typed API検証、正解・不正解・実行失敗・判定エラー表示、timeout、abort、
    二重送信と問題選択・提出responseの競合

非Docker検査は[開発手順](../DEVELOPMENT.md#6-テスト)、Dockerの実行条件とコマンドは、
[Docker統合テスト](../../backend/tests/integration/README.md)を参照してください。

### 不足しているtest

- Docker create応答timeoutとdaemon停止を使うfailure test
- 外側proxyを含むpublic Host allowlistとsecurity header
- 対象main SHAでのOIDC署名・required checks・本番配備の実運用確認（統合候補のCIは確認済み）
- 外側proxyと複数送信元を含む負荷・公平性test

fork bomb、host disk枯渇、daemon停止等は、通常の開発PCで実行しません。
必要な場合は、watchdogとsnapshot復元を備えた使い捨てVMを使用してください。

## 移動した記録へのリンク

<details>
<summary>以前の見出しから記録を開く</summary>

### 2026-10-11のGo標準library更新

[移動先の記録](./dependency-remediation-history.md#2026-10-11のgo標準library更新)を参照してください。

### 2026-10-07の統合候補とGitHub CI

[移動先の記録](./dependency-remediation-history.md#2026-10-07の統合候補とgithub-ci)を参照してください。

### 2026-10-07の統合前候補の検証結果

[移動先の記録](./dependency-remediation-history.md#2026-10-07の統合前候補の検証結果)を参照してください。

### 2026-09-30: frontend libexpatの是正

[移動先の記録](./dependency-remediation-history.md#2026-09-30-frontend-libexpatの是正)を参照してください。

### 2026-09-20の再スキャン記録

[移動先の記録](./dependency-remediation-history.md#2026-09-20の再スキャン記録)を参照してください。

### 更新と互換性

[移動先の記録](./dependency-remediation-history.md#更新と互換性)を参照してください。

### 派生DBの是正

[移動先の記録](./dependency-remediation-history.md#派生dbの是正)を参照してください。

### 同一DBでのscan比較

[移動先の記録](./dependency-remediation-history.md#同一dbでのscan比較)を参照してください。

### Python判定と内蔵Expatの検査

[移動先の記録](./dependency-remediation-history.md#python判定と内蔵expatの検査)を参照してください。

### 回帰検査

[移動先の記録](./dependency-remediation-history.md#回帰検査)を参照してください。

### 残存項目

[移動先の記録](./dependency-remediation-history.md#残存項目)を参照してください。

### 独自sandboxの是正

[移動先の記録](./dependency-remediation-history.md#独自sandboxの是正)を参照してください。

### SOJ-011: DB runtime roleの分離

[移動先の記録](./resolved-issues.md#soj-011-db-runtime-roleの分離)を参照してください。

### SOJ-020: DBのhost port廃止と接続設定の必須化

[移動先の記録](./resolved-issues.md#soj-020-dbのhost-port廃止と接続設定の必須化)を参照してください。

</details>

## Recommended next steps

再開時は、現在のコードでseverityと成立条件を再確認したうえで進めます。

実装順序・依存関係・未決定のreview gateは
[リファクタリングtracker](../refactoring/README.md#roadmap-overview)を参照してください。
この文書では[未解決security課題](#open--partially-resolved--deferred)と
本番環境での確認事項を管理し、完了済みunitを次作業として再掲しません。

SOJ-022の残存指摘と公式修正版を再評価し、mainの同一SHAのCI・署名・承認済みimageの本番反映を確認してください。
[失効したリスク受容・誤検出例外policy](#soj-022の一時許容と撤去条件)と専用処理の撤去は、監査記録を保持する別の変更としてレビューしてください。
その他の課題も1項目ずつ、または密接に関連する小さな単位で差分をレビューして進めてください。

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
