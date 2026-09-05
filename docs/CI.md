# CIとソフトウェア供給網の検査

この文書は、CIの検査範囲、権限、scannerの判定基準、生成物と更新手順の正本です。
ローカルの基本検査は[開発手順](./DEVELOPMENT.md#6-テスト)、実行基盤の制約は
[Docker統合テスト](../backend/tests/integration/README.md)を参照してください。

## Workflowと権限

| Workflow | 検査 | 実行条件 |
| --- | --- | --- |
| FastAPI CI | 対応Python全versionでruff・format・mypy・非Docker test | push、PR、週次 |
| React CI | Node.jsでformat・lint・typecheck・test・build | push、PR、週次 |
| Supply Chain CI / source | workflow検証、Git履歴と作業treeのsecret scan、lock fileのSBOM・脆弱性scan、scanner fixture | push、PR、週次、手動 |
| Supply Chain CI / runtime | sandbox・DBを含む本番5 imageのbuild・SBOM・scan、Compose全問題回帰・browser・image境界・DB更新互換test | push、PR、週次、手動 |
| Supply Chain CI / provenance | 同じrunで検査を通過した生成物の署名付きprovenance登録 | mainへのpushでsource・runtime両jobが成功した場合だけ |

全workflowは`contents: read`を既定とし、checkoutはcredentialを保持しません。
Actionは公式repositoryのfull commit SHAに固定し、runner OS・job timeout・concurrencyを
明示しています。workflowとrefが同じ古い実行は、新しい実行でキャンセルされます。
`pull_request_target`、`workflow_run`、self-hosted runnerは使用しません。
FastAPI CIでは、browser scriptも含めたmypy検査のため`e2e` groupを導入します。
このjobではブラウザ本体を取得・実行しません。

provenance jobだけに`id-token: write`と`attestations: write`を付与します。
このjobはcheckoutや取得artifact内のcode実行をせず、同じrunの生成物だけを取得して
固定済みActionへ渡します。PRには署名権限を付与しません。registryへのpush、release作成、
本番deployはこのworkflowでは行いません。

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
以降のscanでは自動更新を止め、同じjob内で同じDBを使います。Grype reportにDB metadataを残します。
既存依存でも新たなadvisoryでCIが失敗するため、週次結果も確認してください。
現在検出されている課題は[security tracker](./security/README.md)へ記録します。

合成secret、既知の脆弱package、破損SBOMを使うfixtureで、実scannerが所定の失敗を返すことを
確認します。合成値は一時fileへ作成し、追跡対象のsourceや例外リストにsecretを追加しません。

### Python runtimeの期限付き例外

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

## Rootless image検証

専用のGitHub-hosted Ubuntu runnerに、固定versionのDockerをrootlessで構築します。
明示されたUnix socketとdaemonの`SecurityOptions`を確認してからbuild・scan・testを行います。
確認できない場合は失敗し、host上のrootful daemonへfallbackしません。

DBを含む本番5 imageは当該checkoutからbuildし、scanしたimmutable image IDでarchiveへ保存します。
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

- 各対象のSyft JSON、CycloneDX JSON、Grype JSON、検出数summaryとPython例外の評価記録
- scanした本番5 imageの`runtime.tar`。image IDでexportするため、元のtagを保持する保証はありません
- `build-record.json`: 製品version、検査時のcheckout commit、dirty状態、image ID、外部image reference、tool manifest・Python例外policy・生成fileのSHA-256

localのbuild recordは検査対象を追跡する未署名の記録です。既存imageを渡した場合、
そのimageが記録中のcheckout commitからbuildされたことまでは証明しません。
CIでは同じrunのcheckoutからbuildし、mainの検査成功後にGitHubのOIDCを使った
署名付きbuild provenanceを各生成物へ登録します。GitHub上のartifactとattestationを
利用できるrepository planが前提です。

artifactの存在だけで検査成功や本番適合を判断しないでください。promotion時は次を確認します。

1. 対象commitの基本CI・Supply Chain CI・必要なreviewがすべて成功していること。
2. 対象runからartifactを取得し、GitHub CLIの`gh attestation verify FILE --repo YusukeKato/ShellgeiOnlineJudge`
   で署名を検証する。結果のworkflow、source commit、refも承認対象と一致すること。
3. build recordの`product_version`・file hash・image IDと実imageのversionラベルを照合する。frontendはE2E用の同一origin設定でbuildしているため、
   本番の`VITE_*`等への適合も確認する。再buildした別の生成物へ元の署名を流用しないこと。
4. 本番反映は[本番運用](./PRODUCTION.md)に従い、依頼者が承認した対象だけを扱うこと。

この変更ではGitHub上のworkflow実行、OIDC署名、branch protection、required checksの設定変更、
本番promotionを実行していません。repositoryへ反映後、実際のrunと設定を確認してください。
required checksには既存のPython matrix各job、`React Build and Test`に加え、
`Workflow, secrets and dependencies`と`Rootless runtime E2E and image scan`を指定します。
PRでskipされるprovenance jobを必須にはしません。mainへの直接push・review bypassの禁止、
workflowやpin変更のreview保護もGitHub側で設定してください。

## 更新方針

DependabotでActions・Poetry・frontend依存の週次PRを提案します。自動mergeは行いません。
scannerは`ci/tools.json`、Poetry/Yarn bootstrapはworkflowの固定値をreviewして更新します。
本番image digestは[本番運用](./PRODUCTION.md#image-digestの更新)の手順を使用します。

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
poetry run pytest backend/tests/test_ci_policy.py backend/tests/test_supply_chain.py
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
