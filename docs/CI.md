# CIとソフトウェア供給網の検査

この文書は、CIの検査範囲、権限、scannerの判定基準、生成物と更新手順の正本です。
ローカルの基本検査は[開発手順](./DEVELOPMENT.md#6-テスト)、実行基盤の制約は
[Docker統合テスト](../backend/tests/integration/README.md)を参照してください。

## 目次

- [Workflowと権限](#workflowと権限)
- [Scannerと停止条件](#scannerと停止条件)
- [Rootless image検証](#rootless-image検証)
- [生成物と検証・promotion](#生成物と検証promotion)
- [更新方針](#更新方針)
- [ローカルでの検証](#ローカルでの検証)
- [公式資料](#公式資料)
- [問題追加の検査範囲](#問題追加の検査範囲)
- [文書だけの変更](#文書だけの変更)

## Workflowと権限

| Workflow | 検査 | 実行条件 |
| --- | --- | --- |
| FastAPI CI | 対応Python全versionでruff・format・mypy・非Docker test | main push、PR、週次 |
| React CI | Node.jsでformat・lint・typecheck・test・build | main push、PR、週次 |
| Supply Chain CI / source | workflow検証、Git履歴と作業treeのsecret scan、lock fileのSBOM・脆弱性scan、scanner fixture | main push、PR、週次、手動 |
| Supply Chain CI / changes | runtime jobの要否を判定（[文書だけの変更](#文書だけの変更)） | main push、PR、週次、手動 |
| Supply Chain CI / runtime | sandbox・DBを含む本番5 imageのbuild・SBOM・scanと配備archive（`runtime-reports`）の作成 | main push、PR、週次、手動。文書だけの変更では省略 |
| Supply Chain CI / regression | runtimeのarchiveをimage IDで照合して読み込み、Compose E2E・全問題回帰・image境界・DB更新互換test | runtime jobの成功後 |
| Supply Chain CI / browser | 同じarchiveのimageで実ブラウザの提出・表示検査。全問題の画面検査は3 jobへ分割 | runtime jobの成功後 |
| Supply Chain CI / runtime-result | runtime・regression・browserの全成功、または文書だけの変更による全省略を1つの結果にまとめる | 常に実行 |
| Supply Chain CI / provenance | 同じrunで検査を通過した生成物の署名付きprovenance登録 | mainへのpushでsource・runtime・regression・browserがすべて成功した場合だけ |
| Production deploy | 同じcommitの全CI成功待ち、署名検証、SSH配備・DB migration・起動確認 | main push、Repository variableで有効化した場合だけ。配備済みcommitとの差分が文書だけなら省略 |

作業branchへのpushでは検査を重複起動せず、PR作成・更新で検査します。main pushの検査・署名・配備条件は維持します。

全workflowは`contents: read`を既定とし、checkoutはcredentialを保持しません。
Actionは公式repositoryのfull commit SHAに固定し、runner OS・job timeout・concurrencyを
明示しています。検査workflowとrefが同じ古い実行は、新しい実行でキャンセルされます。
Production deployはmigrationの中断を避けるため直列実行し、進行中runを自動キャンセルしません。
`pull_request_target`、`workflow_run`、self-hosted runnerは使用しません。
FastAPI CIでは、browser scriptも含めたmypy検査のため`e2e` groupを導入します。
このjobではブラウザ本体を取得・実行しません。

Supply Chainのprovenance jobに`id-token: write`と`attestations: write`を付与します。
このjobはcheckoutや取得artifact内のcode実行をせず、同じrunの生成物だけを取得して
固定済みActionへ渡します。PRには署名権限を付与しません。registryへのpush、release作成、
本番deployはこのworkflowでは行いません。

Production deployは`workflow_run`を使わず、main pushから読み取りAPIで
Python・React・Supply Chainの同じSHAのpush runを最大55分待ちます。
最新runの失敗を過去の成功で置き換えません。待機jobには`actions: read`、
配備jobにはさらに`attestations: read`とAWS OIDC用の`id-token: write`を付けます。
署名検証後にAWS認証し、SSH秘密鍵はSSM経由の転送stepだけに渡します。
Session Manager pluginは`ci/install_session_manager.sh`の公式deb URL・version・SHA-256へ固定し、
job専用directoryへ展開します。AWS CLIはGitHub-hosted Ubuntu runnerの導入済み版を使用します。
本番の資格情報は`production` Environmentへ限定します。
AWS認証ActionはNode.js 24で動作するため、Actions runner v2.327.1以降が必要です。
GitHub-hosted runnerを使用し、Action更新時は実jobログのrunner versionと公式の要件を照合します。
設定と失敗時の停止・復旧は[自動更新手順](./AUTODEPLOY.md)を正本とします。

## Scannerと停止条件

検証toolのversion、公式配布URL、archive SHA-256は[`ci/tools.json`](../ci/tools.json)を
正本とします。installerはhash照合後に指定の通常fileだけを展開し、専用directoryへ配置します。
未知hashやsymlinkを拒否し、既存の実行fileを上書きしません。現在の配布対象はLinux x86_64です。
アプリケーションのPoetry依存にはscannerを追加していません。

| Tool | 検査対象 | 失敗条件 |
| --- | --- | --- |
| actionlintとCI policy test | YAML、expression、Action入力、権限・固定SHA・timeout・署名job境界 | 構文・policy違反 |
| Gitleaks | shallowでない取得済みGit履歴の全refと、現在の作業tree | secret検出またはtool障害 |
| Syft | Poetry/Yarnのlock file、本番backend・runner・frontend・派生DB、build済み独自sandbox | inventory作成失敗、空inventory、Python/frontendの片側欠落 |
| Grype | 同じSyft inventoryを脆弱性DBと照合 | 下記の期限付き例外を除く修正版のあるHigh/Critical、DB取得・読込失敗、scan失敗、未知のreport形式 |

secret出力は全量redactし、secretを含み得る生のreportをartifactへ追加しません。
lock fileのscanには開発・任意groupも含めます。
ローカルvenvやcacheはinventoryへ混入させず、
Pythonとfrontendの両方が収録されていることを確認します。

脆弱性reportには低severityや未修正のものも含む全件を残します。例外適用前の停止対象は
`High` / `Critical`かつGrypeのfix stateが`fixed`の検出です。未修正の脆弱性が安全であることを
意味せず、運用上の評価は別途必要です。包括的なignore、既存検出の自動baseline化、
期限のない例外は設けていません。例外適用後も停止対象が残れば終了code 2、tool障害は非0で失敗します。
壊れた・欠落したreportを「脆弱性なし」と扱いません。
Grype標準のmatcherによる除外は`ignoredMatches`へ残ります。例えばsandbox内の
kernel header packageに対する間接matchの除外であり、ホストkernelの脆弱性評価を代替しません。

DBは各jobで更新してから使用し、失敗時に古いDBへfallbackしません。
runtime jobではimage buildと並行して更新し、同じstepの終了前に更新の成否を確認してからscanへ進みます。
以降のscanでは自動更新を止め、同じjob内で同じDBを使います。Grype reportにDB metadataを残します。
既存依存でも新たなadvisoryでCIが失敗するため、週次結果も確認してください。
現在検出されている課題は[security tracker](./security/README.md)へ記録します。

合成secret、既知の脆弱package、破損SBOMを使うfixtureで、実scannerが所定の失敗を返すことを
確認します。合成値は一時fileへ作成し、追跡対象のsourceや例外リストにsecretを追加しません。

### Python runtimeの期限付き例外

同梱の旧policyは2026-10-05に失効しています。以下は残っている評価機構の契約であり、現在有効な例外を示しません。
当時の根拠と確認結果は[過去の検証記録](./security/dependency-remediation-history.md#python判定と内蔵expatの検査)、
撤去作業と現在の扱いは[セキュリティ課題](./security/README.md#soj-022の一時許容と撤去条件)を参照してください。

Pythonの公式修正情報とNVDのversion範囲に不一致がある検出だけを、
[`ci/python-runtime-exceptions.json`](../ci/python-runtime-exceptions.json)で管理します。
対象CVE、根拠URL、package、実version、実装fileのhash、確認日・失効日はこのfileが正本です。
これは修正済み実装に対する誤検出の扱いであり、未修正脆弱性のリスク受容には使用しません。

適用には次のすべてを必要とします。

- 対象が本番backendまたはrunnerで、scan対象がimmutable image IDであること
- GrypeのCVE・namespace・package名・型・version・PURLとinstall pathが一致すること
- UTC日付が確認日以降、失効日より前であること。有効期間は最大31日で、自動延長しないこと
- 同じimage IDのPythonとExpatの実version、およびPython実行file・共有library・
  cookies実装・XML拡張moduleのSHA-256がすべて一致すること

実装確認は非root・networkなし・read-only・capability削除・資源上限付きの専用containerで行います。
socketやhost fileをmountせず、終了・timeout・例外時にそのcontainerを回収します。
確認障害や不完全なpolicyはCIを失敗させます。期限切れ、別version、別path、hash不一致は
例外を適用せず、元の停止対象を維持します。hashは確認済みLinux amd64の実装に限定され、
別architectureや再buildされたbinaryへ自動的に適用しません。

Grype JSONは一切書き換えません。summaryの`blocking_before_exceptions`、`exceptions`、
`blocking`で元の停止対象・適用数・適用後の停止対象を区別します。
`backend.python-exceptions.json`と`runner.python-exceptions.json`へ評価時のpolicy、
対象ID、実装確認結果、適用したmatchを保存し、build recordのhash対象にも含めます。
source・frontend・DB・sandboxにはこの例外を適用しません。

失効前に公式advisoryと最新DBを再確認し、不一致が解消されれば例外を削除します。
継続が必要な場合も、根拠・実image・hashを再検証して差分をreviewします。
日付だけの自動更新や、検出を消す目的での対象拡張は行いません。

### 未修正Python脆弱性の一時的なリスク受容

同梱の旧policyは2026-10-04に失効しています。当時の承認は現在の許容を与えません。
以下の評価機構とpolicyは未撤去のため、失効時を含む判定の契約を残しています。

依頼者が承認した未修正脆弱性の一時許容は、修正済み誤検出と区別して
[`ci/python-runtime-risk-acceptance.json`](../ci/python-runtime-risk-acceptance.json)で管理します。
対象CVE・package・実装hash・承認者・評価日・失効日・影響評価・撤去条件はこのfileが正本です。
現在の未解決課題と修正への移行手順は[SOJ-022](./security/README.md#soj-022の一時許容と撤去条件)を参照してください。

上記のimmutable ID・package・install path・実version照合と隔離probeを共用し、
さらに`tarfile.py`を含む全6 fileのSHA-256を照合します。対象はbackend・runnerに限定し、
今回承認されたCVE以外を設定しても拒否します。有効期間は最大14日で、UTCの失効日当日から
許容を適用しません。期限だけの自動延長は行いません。実装不一致なら対象検出は停止対象のままです。
不完全な設定やprobe障害はCI障害とし、他のCVEや製品の停止判定は維持します。

raw Grype reportを保持し、summaryでは`exceptions`（修正済み誤検出）と
`risk_acceptances`（未修正リスクの許容）を分けます。`blocking`は両者の適用後に残る件数です。
`backend.python-risk-acceptance.json`・`runner.python-risk-acceptance.json`に評価時のpolicy、
対象image ID、実装確認結果、適用した検出を保存し、policyと評価記録のhashをbuild recordに含めます。
CI成功やprovenanceは、未修正脆弱性がなくなったことを意味しません。
許容中も全5 imageのscan、E2E、署名、同一commitのCI成功を配備条件とします。

## Rootless image検証

専用のGitHub-hosted Ubuntu runnerに、固定versionのDockerをrootlessで構築します。
`ci/prepare_rootless.sh`でuser systemd・D-Busとcgroupの委譲を準備します。
委譲は`/run/systemd/system/user@1001.service.d/`の一時drop-inと`daemon-reload`で設定します。
既存serviceへの`systemctl set-property Delegate=...`は使用しません。
setup Actionは独自の`XDG_RUNTIME_DIR`と`sudo`を使うため、runnerに限って
`DBUS_SESSION_BUS_ADDRESS`をsudo経由でも保持し、実際のuser busへ接続します。
この準備はGitHub-hosted runner専用です。本番・開発ホストでは実行しません。
backend imageのbuild直後に、scanと同じCPU・メモリ・PID制限付きPython検査を実行します。
user busやcgroup設定の不備はそこで失敗させ、制限の解除や検査のskipは行いません。
明示されたUnix socketとdaemonの`SecurityOptions`を確認してからbuild・scan・testを行います。
確認できない場合は失敗し、host上のrootful daemonへfallbackしません。
setup Actionは終了処理にも`rootless`入力を引き継ぐ版を使用します。
更新時は起動・buildだけでなく、job終了時のrootless daemonのcleanup成功も確認してください。

Dockerの固定versionは[Supply Chain CI](../.github/workflows/supply_chain.yaml)の
`Set up isolated rootless Docker`を正本とします。更新時はActionが参照する
[公式リリース一覧](https://github.com/docker/actions-toolkit/blob/main/.github/docker-releases.json)に
対象の安定版が登録されていることと、[Linux x86_64のstable配布先](https://download.docker.com/linux/static/stable/x86_64/)から
同じversionの`docker`・`docker-rootless-extras`両archiveを取得できることを確認してください。
RC版の存在から正式版の公開を推測せず、`latest`ではなく確認した安定版の番号を指定します。

DBを含む本番5 imageは当該checkoutからbuildし、scanしたimmutable image IDでarchiveへ保存します。
E2E・browser検査のjobは再buildせず、同じrunのarchiveを読み込みます。build recordのarchive hashと
5 imageのIDが一致することを`ci/supply_chain.py`の`load_candidate`で確認してから、`soj-<service>:ci`のtagを付けます。
browser検査用imageは本番imageではないため、browser jobで個別にbuildします。
派生DBのbuild仕様は[本番運用](./PRODUCTION.md#postgresql派生image)を参照してください。
sandboxも`deploy/sandbox/Dockerfile`からbuildし、同じimmutable IDでscan・archive・
統合testを行います。runnerへそのIDを`SANDBOX_IMAGE_ID`で渡します。
失敗した候補にはprovenanceを登録しません。
DB更新互換test用にはDockerfileの正本から公式PostgreSQLのbaseも取得します。
この旧baseは移行元のfixtureであり、本番DBのscan対象はbuild済みの派生imageです。

sandboxの展開には大きな一時領域が必要です。小さなtmpfsを使う環境では、容量のある
作業専用directoryを`TMPDIR`へ指定してください。既存のcacheや他のDocker資源を自動削除して
空きを作る処理はありません。runnerの容量不足やrootless/cgroupの設定不備も検査失敗です。

## 生成物と検証・promotion

source/runtimeのscanを開始した場合は、検出でjobが失敗してもreportを保存します。
保存期間と対象pathはworkflowで固定し、workspace全体やhidden fileをuploadしません。

- 各対象のSyft JSON、CycloneDX JSON、Grype JSON、検出数summaryとPython例外・リスク受容の評価記録
- scanした本番5 imageの`runtime.tar`。image IDでexportするため、元のtagを保持する保証はありません
- `build-record.json`: 製品version、検査時のcheckout commit、dirty状態、image ID、外部image reference、tool manifest・Python例外／リスク受容policy・生成fileのSHA-256

localのbuild recordは検査対象を追跡する未署名の記録です。既存imageを渡した場合、
そのimageが記録中のcheckout commitからbuildされたことまでは証明しません。
CIでは同じrunのcheckoutからbuildし、mainの検査成功後にGitHubのOIDCを使った
署名付きbuild provenanceを各生成物へ登録します。GitHub上のartifactとattestationを
利用できるrepository planが前提です。

artifactの存在だけで検査成功や本番適合を判断しないでください。promotion時は次を確認します。

1. 対象commitの基本CI・Supply Chain CI・必要なreviewがすべて成功していること。
2. 対象runからartifactを取得し、GitHub CLIの`gh attestation verify FILE --repo YusukeKato/ShellgeiOnlineJudge`
   で署名を検証する。結果のworkflow、source commit、refも承認対象と一致すること。
3. build recordの`product_version`・file hash・image IDと実imageのversionラベルを照合する。
   frontendは同一origin APIとRepository variablesの公開リンク、[自動設定する更新日](./AUTODEPLOY.md)でbuildし、同じimageをE2E・配備する。
   再buildした別の生成物へ元の署名を流用しないこと。
4. 自動更新を有効にした環境では、Production deployが上記のCI・署名・image照合を実施する。
   手動反映時は[本番運用](./PRODUCTION.md)に従う。

GitHub上のworkflow実行、OIDC署名、branch protection、required checksとSSH配備の実設定は、
repositoryへ反映後に確認してください。workflowの追加だけでは自動更新は有効になりません。
required checksには既存のPython matrix各job、`React Build and Test`に加え、
`Workflow, secrets and dependencies`と`Rootless runtime E2E and image scan`を指定します。
後者は`runtime-result` jobの名前で、build・regression・browserの全jobの結果をまとめます。
browser jobはshard数によって名前が変わるため、個別にはrequired checkへ指定しません。
PRでskipされるprovenance jobを必須にはしません。mainへの直接push・review bypassの禁止、
workflowやpin変更のreview保護もGitHub側で設定してください。

## 更新方針

DependabotでActions・Poetry・frontend依存の週次PRを提案します。自動mergeは行いません。
通常のversion更新PRの同時作成上限は、各エコシステムごとに
[Dependabot設定](../.github/dependabot.yml)の`open-pull-requests-limit`で管理します。
これはリポジトリ全体の合計上限ではなく、security更新PRには適用されません。
React・React DOMと両方の型定義は、通常のversion更新を同じPRへまとめます。
ReactとReact DOMはlockされた実versionを揃え、既存の画面テストで起動互換性を確認します。
`@types/node`は実行環境と同じmajorを維持し、Dependabotのmajor更新提案を除外します。
Node本体のmajorを移行するときに、型定義・CI・build imageを合わせて見直します。
複数の依存をまとめて更新する場合も、peer dependencyと対応Python・Nodeの条件を照合し、
lock fileを再解決した後に単体・型検査と本番imageの統合検証を行います。
最新版を組み合わせられない場合は、互換性を確認できた版に留め、理由を記録します。
scannerは`ci/tools.json`、Poetry/Yarn bootstrapはworkflowの固定値をreviewして更新します。
本番image digestは[本番運用](./PRODUCTION.md#image-digestの更新)の手順を使用します。

Alpineの配布indexでは旧package revisionが置き換わるため、base imageのdigest固定だけでは
後続の`apk add package=version`の再取得を保証できません。固定versionを取得できなくなった場合は、
対象baseの`apk policy`で配布中のrevisionを確認し、同じpackageを固定しているDockerfileを
合わせて更新します。固定指定を外して回避せず、更新imageのbuild・scan・関連統合testを確認してください。

1. 公式のrelease情報・source commit・配布checksumを確認する。
2. versionとSHAを同じ差分で更新し、tool配布物のhashを照合する。
3. actionlint、policy test、scanner fixture、実依存/imageのscanを実行する。
4. 検出の変化と互換性をreviewする。修正が必要な依存を、一括ignoreで隠さない。

Action SHA・scanner archiveの固定は、第三者artifactの署名検証や完全に再現可能なbuildと
同じ保証ではありません。OS package repository、bootstrapの間接依存、外部registryの
供給元検証などの残存範囲は[security tracker](./security/README.md)で追跡します。

## ローカルでの検証

既存のPoetry開発環境を使い、今回の作業専用directoryへtoolとDBを取得します。
これらの取得とregistry scanには外部ネットワーク接続が必要です。

```sh
export SOJ_CI_WORK="$(mktemp -d)"
python3 ci/install_tools.py "$SOJ_CI_WORK/tools" actionlint gitleaks syft grype
"$SOJ_CI_WORK/tools/actionlint"
poetry run pytest backend/tests/test_ci_policy.py backend/tests/test_supply_chain.py backend/tests/test_deployment.py
"$SOJ_CI_WORK/tools/gitleaks" git . --redact=100 --no-banner --log-opts=--all
"$SOJ_CI_WORK/tools/gitleaks" dir . --redact=100 --no-banner
export PYTHONPATH=backend
export GRYPE_DB_CACHE_DIR="$SOJ_CI_WORK/db"
export GRYPE_CHECK_FOR_APP_UPDATE=false
"$SOJ_CI_WORK/tools/grype" db update
poetry run python ci/supply_chain.py fixtures --tools "$SOJ_CI_WORK/tools" --reports "$SOJ_CI_WORK/fixtures"
poetry run python ci/supply_chain.py source --tools "$SOJ_CI_WORK/tools" --reports "$SOJ_CI_WORK/source"
```

image検証では[本番runtime image・Compose E2E](../backend/tests/integration/README.md)の手順で
現在のコードからbuildしたimageを指定します。report directoryは毎回新しいものを使用します。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
poetry run python ci/supply_chain.py runtime \
  --tools "$SOJ_CI_WORK/tools" --reports "$SOJ_CI_WORK/runtime" \
  --backend soj-backend:compose-test --runner soj-runner:compose-test --frontend soj-frontend:compose-test \
  --db soj-db:compose-test --sandbox soj-sandbox:local
```

## 公式資料

- [GitHub Actionsの安全な利用](https://docs.github.com/en/actions/reference/security/secure-use)
- [署名付きbuild provenance Action](https://github.com/actions/attest-build-provenance)
- [rootless Docker setup Action](https://github.com/docker/setup-docker-action)
- [SyftのSBOM生成](https://oss.anchore.com/docs/guides/sbom/getting-started/)
- [Grypeの結果filter](https://oss.anchore.com/docs/guides/vulnerability/filter-results/)
- [Gitleaks](https://github.com/gitleaks/gitleaks)


## 問題追加の検査範囲

全問題の参照解答・判定・DB保存、共通UI・障害復旧・image境界の検査はPRとmainで維持します。
問題ごとの詳細な画面検査だけを、`soj_tools.problem_review`で選択します。
PRはbase SHAと検査対象merge SHA、main pushはeventのbefore SHAと対象SHAの差分を使います。
問題data・個別問題test・文書（Markdown）だけなら代表例と変更問題、共通code変更・削除・未知file・差分取得不能・週次・手動実行なら全問題です。
詳細な対象と手動指定は[Docker統合テスト](../backend/tests/integration/README.md#問題追加時の画面検査)を正本とします。
画像はbrowser jobごとの`browser-ui-review-<job番号>` artifactへ14日保存します。新問ごとにartifact stepを増やしません。

配備ログに転送時間・host更新時間を出します。
短縮効果はこれらとjob時間で測定し、並列jobやCI待機時間を重複加算しません。

## 文書だけの変更

本番imageへ入らないMarkdownだけの変更では、Supply Chainのruntime・regression・browser job（image build・scan・E2E・配備archive作成）と
本番配備を省略します。`Rootless runtime E2E and image scan`（runtime-result）はこの省略を成功として報告します。判定は`ci/deploy.py`の`documentation_only`を正本とします。

- 対象は拡張子`.md`のfileだけです。`problems/`、`frontend/src/`、`frontend/public/`、
  `backend/soj_backend/`・`backend/soj_runner/`・`backend/soj_shared/`、`deploy/`配下はMarkdownでも対象外です。
  `problems/`はfrontend imageから配信され、他もimageや配備処理へ入り得るためです。
- 空の差分、差分取得の失敗、GitHub APIの障害は判定不能として、省略せず全検査・配備します。
- PRはbase SHAと比べます。main pushは直前のpushではなく、**本番更新を確認できた最新commit**と比べます。
  Supersededで配備されなかったコード変更の後に文書だけのcommitが来ても、未配備のコードを検査・配備するためです。
- 本番更新の確認は、配備jobが本番の`.soj-deploy/current.json`を読み戻し、対象commitと一致した場合だけ
  `Record completed production update` stepを実行して記録します。Deployments APIの成功はSuperseded時も
  記録されるため根拠にしません。直近30回のdeploy runに記録がなければ省略しません。
- Supply Chainの`changes` jobはdeploy runを読むため`actions: read`を持ちます。書き込み権限は持ちません。
- Production deployの待機jobは、全CIの成功後に改めて配備済みcommitと比べます。concurrencyで他の配備が
  終わった後の判定なので、Supply Chain開始時より新しい基準を使います。配備が必要なのにruntime jobが
  省略されていた場合は、archiveがないため失敗します。同じcommitのSupply Chain CIを再実行してから、
  Production deployを再実行してください。
- 週次・手動実行では常にruntime jobを実行します。FastAPI CI・React CI・Supply Chainのsource jobは常に実行します。

## CA信頼ストアの検査

Pythonの依存取得前にCI runnerのOS CAを更新し、
[`ci/bootstrap_pip.py`](../ci/bootstrap_pip.py)で公式SHA-256を照合したpip wheelをoffline installします。
単に`PIP_CERT`を指定するだけでは、pipの同梱certifiが残る構成を保護できません。
Dockerfileの共通Python stageではensurepipのseedも更新し、新しいvenvへの旧pip再導入を防ぎます。
Node.js・Goの固定値は各Dockerfileを正本とします。browser内のPlaywright driverは
`NODE_OPTIONS=--use-openssl-ca`で更新済みOS CAだけを使用します。

runtimeとPython・Node・Go・問題dataのbuild stageのscan前、およびbrowser image作成後に、
[`ci/check_ca_trust.py`](../ci/check_ca_trust.py)を実行します。
検査はrootless Docker上の通信不可・read-onlyの一時containerから、OS bundle、
存在するhashed directory、Pythonのcertifi・pip・ensurepip、Poetryが使用するPython向けの
virtualenv seed、Nodeの内蔵bundleを読み取ります。Playwright専用NodeのOS CA選択も必須とします。
[固定の公開証明書fixture](../backend/tests/fixtures/emudhra/README.md)で、漏えいCA経由の
12 chainがissuer不信頼で拒否され、正常なSOJ chainが許可されることを同時に確認します。
時刻を採取日に固定するため、将来の証明書期限切れを是正成功とは扱いません。
sandboxのruntimeにはCAを追加せず、既存のnetwork隔離検査を維持します。

localでの実行には、Python開発依存・OpenSSL CLI・明示したrootless socket・build済みimageが必要です。
稼働serviceや本番volumeは操作しません。失敗時は以降のscan・配備へ進まず、
失敗したstoreとDockerfile・lockを修正して再buildし、同じ検査を再実行します。

```sh
# repository root。image名は今回buildした専用tagへ置き換える。
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
poetry run python ci/check_ca_trust.py \
  soj-backend:ca-check soj-runner:ca-check soj-frontend:ca-check soj-db:ca-check
```

各storeに`12 distrusted, legitimate control accepted`が表示され、終了code 0なら合格です。
base digest・依存lock・CA packageの更新が必要であり、containerの再起動や`--pull`だけでの
固定digestの再取得を、CAの是正として扱いません。
