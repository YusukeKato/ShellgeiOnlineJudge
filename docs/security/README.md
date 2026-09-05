# セキュリティ課題と対応状況

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

- 最終コード照合日: 2026-09-05
- branch: `main`
- 確認対象commit: `66bbc24`とR3-029のpackage再配置review待ち差分
- commit subject: `docs: record approved Python scan exceptions and baseline`
- 今回の変更開始時のworktree: clean
- 対象: repositoryのコード・設定・文書・テストの照合
- 直近の変更: R3-029の責務別package再配置。共有から専用実装への依存を外し、判定・Pillowをbackendへ限定。
  検証結果は[リファクタリングtracker](../refactoring/README.md#r3-029-organize-shared-backend-and-runner-packages)を参照
- 対象外: 本番host、外側reverse proxy、WAF、実際の本番DBと監視基盤

baseline以降に変更がある場合は、先に差分を確認してください。

```sh
git status --short
git log -1 --oneline
git diff 66bbc24
```

## Current security status

- SOJ-022のアプリ依存・nginx・派生DB更新でlock file、frontend・DB imageの停止対象は0件です。
  backend・runnerは修正済みPythonの期限付き例外を各3件適用し、適用後の停止対象は0件です。
  sandboxの残存検出により、image側のCI gateは引き続き失敗します。
  scannerのseverityとサービスでの悪用可能性は区別し、残存項目はSOJ-022で追跡します。
- インターネット公開には、外側proxyまたはWAFの
  実client単位の受付制御を別途確認する必要があります。
- runner異常終了後のsandboxは再起動時に回収します。
  Docker daemon単独の有効期限はないため、SOJ-002を部分解決として追跡します。
- read-only root、tmpfs容量・inode、CPU、memory、swap、PID、
  capability、network、IPC、timeout等の主要sandbox制限は実装され、
  現在のrootless開発環境で実効値を確認しています。
- backendからDocker socketを外し、認証付き内部runnerへ分離した設計は有効です。
  ただし、runnerと他serviceは同じrootless daemonとVMを共有しています。
- R3-023ではbackend・runnerを用途別の非root imageへ分離しました。
  DB runtime roleの権限は維持しているため、SOJ-011は部分解決です。
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
  - 関連: `backend/soj_runner/container_manager.py`、`backend/soj_runner/main.py`
  - 次: runner再起動・回収失敗の監視と、独立した期限強制の要否を判断
- `SOJ-006` — Medium / P1 / Deferred
  - 概要: runner侵害時の影響が同一daemon上のDB、frontend、TLS鍵へ及ぶ
  - 関連: `docker-compose.yml`
  - 次: runner専用hostまたは使い捨てVMへ分離
- `SOJ-011` — Medium / P2 / Partially resolved
  - 概要: backend・runnerの非root化、runtime依存分離、read-only化は実装したが、DB runtime roleの権限が大きい
  - 関連: `backend/Dockerfile`、`docker-compose.yml`
  - 次: migration実行者と常時稼働backendのDB owner/app role・credential分離を設計
- `SOJ-012` — Medium / P2 / Partially resolved
  - 概要: DB行数・Docker service logは制限したが、host I/O、
    DB volume、image cacheにquotaがない
  - 関連: `docker-compose.yml`、`backend/soj_backend/execution_log_retention.py`
  - 次: 専用filesystem、I/O制御、quota、監視を本番設計へ追加
- `SOJ-019` — Medium / P2 / Partially resolved
  - 概要: CI権限・timeout・Action SHA、secret/依存/image scan、SBOMとmain限定provenanceを構成した。
    GitHub上の実行、required checks・review保護、供給元署名と本番promotionは未確認または未導入
  - 関連: `.github/workflows/`、[CI文書](../CI.md)
  - 次: 実CIとOIDC署名を確認し、required checks・workflow変更のreview保護を設定する。
    bootstrapの間接依存・第三者imageの供給元検証とpromotion方針を整備する
- `SOJ-022` — High/Critical（scanner分類） / P1 / Partially resolved
  - 概要: アプリ依存・nginx・派生DBを是正。Pythonは実装確認付きの期限付き例外で扱い、sandboxの検出が残る
  - 関連: `pyproject.toml`、`poetry.lock`、`frontend/yarn.lock`、`frontend/Dockerfile`、`deploy/postgres/Dockerfile`、`ci/python-runtime-exceptions.json`、runtime image
  - 確認: [是正記録](#soj-022依存imageの是正記録)に変更範囲、検出比較、未解決範囲を記載
  - 次: sandboxの修正版候補を検証し、Python例外の期限前に公式advisory・DBと実装を再確認する。
    本番反映とGitHub上のCI確認は未実施
- `SOJ-020` — Low / P3 / Deferred
  - 概要: DBをloopback公開し、Compose外では弱いfallback URLがある
  - 関連: `docker-compose.yml`、`backend/soj_backend/database.py`
  - 次: 本番port非公開化と設定fail-closedを検討
- `SOJ-021` — Low / P3 / Partially resolved
  - 概要: command/output保持の目的・最小field・backup方針は確定したが、
    非公開脆弱性報告手順は未整備
  - 関連: `backend/soj_backend/models/execution_log.py`、
    `backend/soj_backend/execution_log_repository.py`、`SECURITY.md`
  - 次: security contactと非公開報告手順を決定

現在の未解決trackerは次の内訳です。

- Open: 0件
- Partially resolved: 6件
- Deferred: 2件
- Severity: High/Critical 1件、Medium 5件、Low 2件

## SOJ-022：依存・imageの是正記録

2026-09-05、依頼者の次の対策実装依頼に対し、CIを停止させるP1課題を優先しました。
アプリ依存・nginxの是正は依頼者のreview承認後、`cb044c7`でcommit済みです。
派生DBの是正は依頼者のreview承認後、`6b59c19`でcommit済みです。
Pythonの期限付き例外は依頼者のreview承認後、`4120a76`でcommit済みです。
sandboxと期限付きで扱うscanner判定の残存課題があるため、
SOJ-022全体を`Resolved`にはしていません。R3-029等のpackage再配置は今回の範囲外です。

### 更新と互換性

- FastAPIを0.116.2から0.136.3へ更新し、Starletteを0.48.0から1.6.0へ解決しました。
  旧FastAPIのStarlette上限が修正版の取得を妨げていました。公式の依存条件に従い、
  [大きな内部変更を含む0.137以降](https://fastapi.tiangolo.com/release-notes/#01370-2026-06-14)への移行は分けています。
- urllib3を2.6.3から2.7.0、開発用の型stubから入るcryptographyを46.0.5から50.0.1へ更新しました。
- frontendの間接依存flattedを3.3.3から3.4.4、browserslistを4.25.2から4.28.9へ更新しました。
  browserslistが必要とするdata packageもlockへ反映しました。直接依存の追加・一括更新はしていません。
- nginxの固定digestを更新しました。正本は`frontend/Dockerfile`で、実nginx統合testのimageも揃えています。
- クリーンvenvでmypyがE2E scriptのPlaywrightを見つけられないことを確認したため、
  FastAPI CIと開発手順で既存の`e2e` groupを明示しました。本番runtime依存への追加はありません。

Starletteのform解析・StaticFilesに関する検出経路は本サービスの提出処理では使いませんが、
framework全体の依存を修正版へ更新しています。urllib3はDocker SDKのHTTP処理、
cryptographyは開発用の間接依存、flatted・browserslistはfrontendの検査・build依存です。
到達性の違いを理由とした検出除外は追加していません。

### 派生DBの是正

公式PostgreSQL 15 baseを維持し、OpenSSLとgosuのbuildを更新しました。
実装・固定値・更新時の制約は[PostgreSQL派生image](../PRODUCTION.md#postgresql派生image)を正本とします。
CIとすべてのDB統合testはbuild済みの派生imageを使用し、scan・archive・build recordの対象にも含めます。
公式baseをそのまま起動するのは既存volume互換性testの移行元だけです。検出除外・gateの緩和は追加していません。
DBの停止対象42件は0件になりました。Medium 3件（BusyBox系）とLow 1件（gosu内のx/sys）はreportに残ります。

### 同一DBでのscan比較

R3-025と同じ固定scannerと、2026-09-05に取得した同一の脆弱性DBで比較しました。
アプリ3 imageは`cb044c7`の依存更新時に再buildし、DBは今回のDockerfileからbuildした派生imageです。
sandboxは固定digestを維持し、既存SBOMを同じDBで再照合しています。
停止条件の正本は[CI文書](../CI.md#scannerと停止条件)です。

| 対象 | 依存・image更新前 | 依存・image更新後 | Python例外適用後 |
| --- | ---: | ---: | ---: |
| Python / frontend lock file | 12 | 0 | 0 |
| backend image | 6 | 3 | 0 |
| runner image | 8 | 3 | 0 |
| frontend image | 20 | 0 | 0 |
| PostgreSQL | 42 | 0 | 0 |
| sandbox | 248 | 248 | 248 |

対象ごとのmatch数であり、重複を除いたCVE数ではありません。source scanは終了code 2から0へ改善しました。
image側は残存検出によりCIを停止します。低severity・未修正の検出を含め、全脆弱性がなくなったという意味ではありません。

### Python判定と内蔵Expatの検査

backend・runnerの各3件はPythonの公式修正情報とNVDのversion範囲の不一致です。
例外の対象・根拠・期限・実装hashは[`ci/python-runtime-exceptions.json`](../../ci/python-runtime-exceptions.json)、
適用条件と失効時の挙動は[CIの期限付き例外](../CI.md#python-runtimeの期限付き例外)を正本とします。
現行の固定image、Python対応範囲、アプリ依存lockを維持しています。
`4120a76`の検証ではGrypeのraw検出をbackend 193件・runner 194件のまま保持し、そのうち各3件を例外へ分類しました。
包括的なignoreやscanner自体のfilterは追加していません。

Python 3.13.15の公式image候補もbuild・scanしました。停止対象は各0件でしたが、
実binaryのExpatが2.8.2で、現行2.8.3に含まれる
[CVE-2026-72522の修正](https://blog.hartwork.org/posts/expat-2-8-3-released/)が欠けるため採用しませんでした。
Syftはこの内蔵Expatをpackageとして識別しておらず、scan成功だけではこの後退を検出できません。
本番runtime統合testへPythonとExpatの実version検査を追加し、この更新候補を拒否できるようにしました。

### 回帰検査

アプリ依存・nginxの是正（`cb044c7`）:

- 新規venvでPython 3.14のruff・format・mypy・非Docker 541件が成功。
  `e2e` group不足によるmypy失敗も再現し、明示install後の成功を確認しました。
- frontendのformat・lint・typecheck・test 35件・production buildが成功。
- 更新した本番3 imageをbuildし、rootless Docker 19件がすべて成功。
  Composeの全92問、browser、認証・revision拒否、DB/runner停止復帰、
  直接sandbox経路の全92問、nginx・migration・runtime境界検査を含みます。
- actionlintとlock整合性検査が成功。GitHub-hosted上のworkflow、OIDC署名、
  required checksと本番への反映は実行していません。

派生DBの是正（`6b59c19`）:

- Dockerfileの固定base・Composeのbuild対象を検証するtestと、E2EのDB image指定testで実装前のREDを確認。
- Python 3.14のruff・format・mypy・非Docker 542件が成功。
- 旧PostgreSQLの専用volumeを派生DBで読み書きし、旧imageへ戻してdata保持・非root PID 1・正常停止を確認。
- 派生DBを指定したrootless Docker 20件が成功。Compose・直接sandbox両経路の全92問、browser、
  migration、認証・停止復帰、runtime境界を含む。アプリ3 imageは前回の検証済みimageを再利用した。
- 派生DBを含む本番4 imageのarchive・build recordを生成し、OCI indexとscan済みimmutable IDの一致を確認。
- frontendのコード・依存・imageは変更していないため、基本5検査は前回の成功結果を維持し、今回は再実行しない。
- rootless Compose設定検査とactionlintが成功。GitHub上のCI・署名実行、本番DBへの反映は未実施。

Pythonの期限付き例外（`4120a76`）:

- 新しい例外testで実装前のREDを確認。期限切れ、未知CVE、別namespace・package・path、
  version/hash不一致、確認障害、rootful拒否、timeout時のcontainer回収、raw report保持を検証した。
- Python 3.14のruff・format・mypy・非Docker 573件が成功。
- 同じ固定scanner・DBで現行の両imageを再scanし、実version・5 fileのhash照合と各3件の例外適用を確認した。
  適用記録とpolicy hashを含むbuild recordを生成。実scannerの合成secret・脆弱package・破損SBOM fixtureも成功。
- 採用する現行imageでrootless runtime統合4件が成功。非root・収録境界・socket補助group・内部通信・判定・DB保存を含む。
- 不採用の3.13候補では全Docker 20件（Compose・直接sandboxの全92問、browserを含む）が成功したが、
  追加したExpat下限検査には不合格となる。これを採用imageの全回帰結果には数えない。
- 最終差分はCI判定・検査と文書に限定され、frontendの基本5検査と採用imageの全Docker回帰は再実行していない。
  採用image・依存・API・sandboxは前回検証済みのものを維持。GitHub上のCI・署名・本番反映は未実施。

### 残存項目

- backend・runnerの各3件は`CVE-2026-3644`、`CVE-2026-4224`、`CVE-2026-7210`です。
  [Python 3.12.14の公式修正情報](https://www.python.org/downloads/release/python-31214/)と、
  [Expat修正条件を含む公式リリース説明](https://blog.python.org/2026/08/python-31214-31116-31021/)を確認しました。
  実imageはPython 3.12.14／Expat 2.8.3であり、修正済みversionに対するscanner判定の不一致です。
  期限付き例外でCIの停止対象から区別していますが、NVD側の判定が訂正されたことを意味しません。
  期限前に再評価し、DB側で不一致が解消した場合は例外を削除してください。
- sandboxは多数の言語runtime・配布済みbinaryを含みます。個別toolの更新と問題互換性の検証が必要です。
  更新候補`sha256:1916181574c13e207836852d673bcf367c8293b7b556acbcaf0bc3f2f660d6b2`を
  registryからSBOM化して比較しましたが、停止対象は248から245件への減少にとどまり、
  `jackson-core`の`GHSA-r7wm-3cxj-wff9`が新たに検出されました。
  この候補は今回採用せず、現行digestと問題互換性を維持しています。
  候補のコマンド実行・全問題回帰は未実施で、採用時に改めて検証が必要です。

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

RES-003、RES-007、RES-008、RES-009、RES-011、RES-012、RES-013、
RES-014、RES-015、RES-016、RES-017、RES-018、RES-019、RES-020、RES-021、RES-022、
RES-023、RES-024、RES-025、RES-026は、
記載した範囲では解決済みです。
daemon単独のsandbox有効期限等の残存経路は、
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

### SOJ-011: DB runtime roleの分離

R3-023のOS user・image分離後も、backendは起動時migrationのため既存のDB roleを
使用します。migration用の資格情報を常時稼働backendへ渡さない構成、既存volumeの
権限移行、rollback手順を合わせて設計する必要があります。SOJ-006の同一daemon上の
影響範囲も、このimage分離だけでは解消しません。

## Deferred issues

### Architecture変更が必要

- SOJ-006は、runnerを専用hostまたは使い捨てVMへ移す必要があります。
  現在の内部HTTPは平文・固定URLであり、そのまま別hostへ公開してはいけません。

### Product方針が必要

- SOJ-021の非公開脆弱性報告窓口は、運用判断が必要です。

### CI・運用基盤が必要

- SOJ-019は、構成したCIの実運用確認、review保護、第三者供給元検証、
  artifact promotionの整備が必要です。
- SOJ-020は、本番のDB管理方法を決めてからport公開を分離します。

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
  - 現在の92問の正解commandとjudge互換性
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
- GitHub上でのCI・OIDC署名・required checksの実運用確認
- 外側proxyと複数送信元を含む負荷・公平性test

fork bomb、host disk枯渇、daemon停止等は、通常の開発PCで実行しません。
必要な場合は、watchdogとsnapshot復元を備えた使い捨てVMを使用してください。

## Recommended next steps

再開時は、現在のコードでseverityと成立条件を再確認したうえで進めます。

実装順序・依存関係・未決定のreview gateは
[リファクタリングtracker](../refactoring/README.md#roadmap-overview)を参照してください。
この文書では[未解決security課題](#open--partially-resolved--deferred)と
本番環境での確認事項を管理し、完了済みunitを次作業として再掲しません。

SOJ-022のscanner検出を優先して評価し、検査を停止させる依存・imageの更新範囲を決めてください。
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
