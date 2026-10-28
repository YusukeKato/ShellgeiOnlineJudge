# 依存関係・image是正の検証記録

この文書はSOJ-022に関する過去の調査・scan・承認・検証記録です。
各節の日付・commit・検査範囲に限った結果であり、現在の安全性や本番配備の完了を保証しません。
記録中の「現在」「今回」「次」は、その記録時点を指します。
期限切れの例外・リスク受容は、現在の許容を与えるものではありません。
現在の課題と次の作業は[セキュリティ課題の入口](./README.md)、
現行のCI判定は[CI文書](../CI.md#scannerと停止条件)を参照してください。

## 記録の目次

- [2026-10-28: runtime修正更新](#2026-10-28のruntime修正更新)
- [2026-10-25: Brotli・Zod・Undici更新](#2026-10-25のbrotlizodundici更新)
- [2026-10-22: frontend curl/libcurl削除](#2026-10-22のfrontend-curllibcurl削除)
- [2026-10-21: certifi信頼ストア更新](#2026-10-21のcertifi信頼ストア更新)
- [2026-10-19: frontend nginx・X11/XPM更新](#2026-10-19のfrontend-nginxx11xpm更新)
- [2026-10-11: Go標準library更新](#2026-10-11のgo標準library更新)
- [2026-10-07: 統合候補とGitHub CI](#2026-10-07の統合候補とgithub-ci)
- [2026-10-07: 統合前候補](#2026-10-07の統合前候補の検証結果)
- [2026-09-30: frontend libexpat是正](#2026-09-30-frontend-libexpatの是正)
- [2026-09-20: 再scan](#2026-09-20の再スキャン記録)
- [失効した一時許容と撤去条件](#soj-022の一時許容と撤去条件)
- [依存・imageの是正記録](#soj-022依存imageの是正記録)

## SOJ-022の現在の停止対象

### 2026-10-28のruntime修正更新

基準commitはa69b6a44a734deee2bcede20c6785d2696d0fa49。10/28の利用者承認で、
問題追加より先に保守修正を検証し、本番反映まで進めます。

- 共通Python baseと独立したbrowser baseを同じ3.12.16の公式tag/digestへ更新します。
  [公式release](https://www.python.org/downloads/release/python-31216/)には
  eMudhra中間CA鍵の拒否、Expat 2.9.0等が含まれます。公開入力からExpatの脆弱処理への到達は未確認です。
  build時のHTTPS取得で使うPython sslを更新し、既存のCA・pip bootstrap対策も維持します。
  全setup-pythonは固定Action SHAと対応minor範囲を維持し、最新patchを取得します。
- Ubuntu sandboxのlibbrotli1を[USN-8956-1](https://ubuntu.com/security/notices/USN-8956-1)の修正版へ固定します。
  [CISA KEV](https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json)へ
  CVE-2026-111497が10/27追加されましたが、SOJの侵害やsandbox外への悪用を確認したものではありません。
  frontendのBrotliは既に修正済みで、別の配布packageとして扱います。
- PostgreSQL15の同じbase・server・entrypoint・PGDATAを維持し、libcrypto3/libssl3を同版の
  [Alpine stable package](https://github.com/alpinelinux/aports/blob/3.24-stable/main/openssl/APKBUILD)へ限定更新します。
  NVD分類の全CVEやQUIC/DTLSをSOJで悪用可能と一般化しません。
- frontend/DBのmusl-utilsを、既に修正済みのmusl本体と同じAlpine revisionへ揃えます。
  [公式secfix](https://github.com/alpinelinux/aports/blob/3.24-stable/main/musl/APKBUILD)は
  CVE-2026-107891のregcomp整数overflow修正を含みます。新規toolやlibc系列を追加しません。
- 両runtimeのFastAPIからの推移依存OpenTelemetry APIを1.45.1へ、lock entryと配布hashだけで更新します。
  [GHSA-xcq7-p3pf-p88h](https://github.com/advisories/GHSA-xcq7-p3pf-p88h)はtracestateの二乗時間parseの修正です。
  SDK/exporterや直接依存を追加しません。SOJでの明示的instrumentationと公開経路のDoS成立は未確認です。

更新前の小さな確認では、OpenTelemetry1.45.0は通常形式32 entryからなる8,245文字のheaderと、
通常のa=bを受理しました。候補1.45.1の実wheelでは、正規表現の分割が通常の文字列分割と
各memberの検査へ置き換わっています。一方、release/advisoryに記載された8,192文字超の拒否は
同wheelで確認できず、上記8,245文字も受理します。この上限保証は主張せず、修正版の実収録と
正常header、任意空白、重複key拒否の互換性を実imageで検査します。
既存nginx・HTTPのheader制限は維持し、独自のparserや依存patchを追加しません。
大量空白によるCPU負荷試験は実施しません。Python/Expatの実収録下限、browserとのbase一致、
全setup-python経路とsandbox・frontend・DBの修正版を既存testで要求し、metadata遅延による後退を拒否します。

基本検査、rootlessのCA・image境界・対象library、専用volumeでのDB旧→新→旧互換性を確認し、
全5image/source scan・全問題回帰・共通browser・配備検査は対象headのCIでも必須とします。
skipや未実施は成功として数えません。検証結果、最終head、CI・署名・本番確認はPRへ記録します。
本番hostのkernel・Docker/containerd/runc/RootlessKit・CA、外部Actionのbundled Undiciは別管理です。
API・DB schema、132問、sandbox・TLS制限、scan停止条件・例外policyは変更しません。
アプリ更新完了をhost是正や全脆弱性0と表現しません。

ローカル候補の検証ではRuff・format・mypy（171 files）と非Docker1,036件が成功しました。
rootlessの23件（全132問の参照解・DB更新と復帰・日英画面の提出保存を含む）と、
上記の誤ったheader上限期待を訂正した両runtime境界2件が成功し、skipはありません。
browserのPython/Expat実測、5imageのCA storeで各12漏えいchain拒否と正常chain許可も確認しました。
CAを持たないnetwork分離sandboxをCA検査へ誤指定した実行は失敗として記録し、既存CIの対象へ合わせました。
候補sourceと5製品は同じ最新確認済みDBで停止対象・例外・リスク受容0でしたが、
非停止matchはbackend166、runner166、frontend3、DB5、sandbox957件が残ります。
source matchは0です。修正版のBrotliにも古いvendor metadata由来のmatchが残るため、実収録版と公式USNを併用します。
独立した差分reviewの文書上限表記は訂正済みで、具体的なruntime bypass・互換性回帰は指摘されませんでした。

### 2026-10-25のBrotli・Zod・Undici更新

基準commitは旧本番と同じ`0d6b20f29ba7e744180c22e9b2e3c7d664606b47`。
同commitの配備済みSBOMを2026-10-24 17:45:29 UTC作成のDBで再照合し、
frontendのBrotliにCritical、source lockのZod・UndiciにHighの修正可能な指摘を確認した。
監視通知後、利用者が3件の限定更新と検査後の本番反映を承認した。

- Brotli: [公式release](https://github.com/google/brotli/releases/tag/v1.2.1)と
  [Alpine secfix](https://gitlab.alpinelinux.org/alpine/aports/-/blob/3.24-stable/main/brotli/APKBUILD)に従い、
  frontendへ収録されたdecoder libraryを同じstable系列の修正版へ更新する。
  nginx image-filter moduleからlibgd・FreeTypeを経由するpackage依存があるが、
  SOJ設定は静的配信とAPI proxyで、公開入力から脆弱なdecode処理へ至る経路は未確認。
- Zod: [GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5)の修正版へlockを更新する。
  eslint関連の開発依存であり、公開APIのJSON検査はZodを使用しない。
  上流修正は上限を指定したcollectionの要素検査前のサイズ判定であり、
  上限のないcollection全般の資源消費を防ぐ保証とは扱わない。
- Undici: [GHSA-xjj6-f33q-929c](https://github.com/advisories/GHSA-xjj6-f33q-929c)と
  [8.12.2 release](https://github.com/nodejs/undici/releases/tag/v8.12.2)に従いlockを更新する。
  jsdom経由の開発依存で、利用者のブラウザfetchとは別の実装。
  Node内蔵版とnpm packageも別のcopyとして確認する。
  過剰なcontent-encodingと早期切断による異常終了の攻撃試験は実施しない。

変更はfrontend Dockerfileのpackage固定、lockの対象2 entry、既存実image検査のBrotli確認と関連文書。
package.json・依存元・公開API・nginx設定・CA・curl不在・sandbox制限は維持し、
scan例外やリスク受容を追加しない。修正版とhashはDockerfile・lockを正本とする。

検証では少量のarray/setをinterpreter・compiled両設定で旧版と比較し、
上限超過時の要素callbackが旧版3回から候補0回となり、通常2項目は両版とも受理された。
Undiciはloopbackの短い応答で小文字・大文字・混合大小文字のSRIを比較し、
候補では不一致hashを全て拒否し、一致hashは全て受理した。
これは修正版に含まれるSRI修正の検証であり、上記Highの異常終了自体の再現試験ではない。

ローカル候補の検証:

- Ruff lint・format、mypy（171 files）、非Docker 1,032件、frontendのformat・lint・typecheck・81 test・buildが成功。
  Windows checkout由来の既存改行差は検証用コピー／stdinだけでLF化し、作業treeの無関係な内容は保持した。
- 新問の非Docker 2件と、32 sandbox実行を含むrootless個別検査が成功。
- frontendの実image検査3件が成功。CA 2 storeは漏えいchain各12件を拒否し、正常chainを許可した。
- 固定hashを検証したSyft v1.52.0・Grype v0.119.0と上記DBを使用。更新確認は新DBなし。
  sourceは319 packages / findings 1、frontendは65 packages / findings 4、いずれも停止対象・例外・リスク受容0。
  対象Brotli・Zod・Undiciの指摘は残らず、OpenTelemetryのMediumとBusyBoxのMedium 3件、
  musl-utilsのUnknownは残る。停止対象0は脆弱性0を意味しない。
  frontend候補の不変IDは`sha256:cd45db60d35b6502777dd0b98da93e12b6a504cbd64cecf8f019aa2e92cd675d`。
- 独立した読み取り専用の差分レビューで、具体的な残存bypass・回帰は指摘されなかった。

全5 image・全問題回帰・共通ブラウザ・配備検査はCIで必須とし、同じ全件をローカルで重複実行しない。

本番host、他imageの非停止指摘、DB OpenSSL・OpenTelemetry・musl-utils等の別候補は更新対象外。
本記録は候補の限定検証であり、全脆弱性0やhost更新完了を意味しない。
最終headのCI・署名・配備・公開確認は当該PRに残す。

### 2026-10-22のfrontend curl/libcurl削除

基準commitは`fc781be7b32df11eecb6dae9832d1e1a2d0fe667`。
同commitの配備済みfrontend SBOMでcurl/libcurl 8.22.0-r0、Alpine 3.24.2を確認した。
[curl公式advisory](https://curl.se/docs/CVE-2026-92392.html)のCVE-2026-92392は、
HTTP/2のupload中に悪意ある接続先が返すRST_STREAMによりuse-after-freeが発生する問題で、
上流8.23.0等に修正がある。同系列の[Alpine package](https://pkgs.alpinelinux.org/package/v3.24/main/x86_64/curl)は
確認時点で8.22.0-r0のため、edgeへの切替や独自curl buildを追加せず、SOJで不要なclient/libraryを削除する。

ブラウザはfetch、nginxはnative proxyで通信し、frontendの起動scriptとComposeにcurl呼出しはない。
APIへ受け取った提出commandは別のsandboxで実行されるため、今回のfrontend package削除の影響を受けない。
画面に表示するcurl例は利用者の端末で実行するため、その表示も維持する。
公開requestから該当HTTP/2 upload処理へ到達する経路や、実際の悪用は確認していない。

固定baseの通常の依存解決でcurlを削除するとlibcurlと、curl/libcurlだけが必要としていた5 libraryも削除される。
nginxの依存を強制削除せず、libcurlが残ればbuildを失敗させる。
修正候補ではnginx binary・全14 module・entrypointと4 scriptのhashが旧imageと一致し、
libcurlへのELF依存がなく、CA bundleのhashと両CA packageも維持されることを確認した。
実imageの回帰testはpackageのほかcurl/wcurlの別名・標準pathの共有libraryの再収録も拒否する。
scannerの停止条件・例外、TLS検証、API・sandboxの隔離・制限は変更しない。

ローカル検証:

- 追加した不在testは旧imageでcurlを検出して失敗し、候補imageのfrontend検査3件は成功。
- Ruff lint・format、mypy（163 files）、非Docker 1,024件が成功。
- frontendのformat・lint・typecheck・test 81件・production buildが成功。
- 実imageのCA 2 storeは漏えいchain各12件を拒否し、正常controlを許可。
- HTTPS/API・browser E2Eの2件が成功。正解・誤答・timeout・出力上限・画像判定・DB保存、
  日英画面と代表問題の実ブラウザ操作を確認。端末向けcurl例はfrontendの6 testで確認。
- Grype v0.119.0・Syft v1.52.0の配布hashを検証し、確認時の最新DB
  （2026-10-21 06:31:02 UTC作成）で候補の不変image IDをscan。
  65 packages / findings 3、停止対象・例外・リスク受容0。
  curl/libcurl packageと対象CVEは検出されず、残る3件はBusyBox系のCVE-2025-60876（Medium）。
  停止対象0は全脆弱性0を意味しない。候補image IDは
  `sha256:bcc974c07894cb93a391aeceaa25e76b875eac2e2980362afdd4b1d9e5e92c1c`。
- 文書4件の相対リンク・見出し119件とgit diffの空白検査が成功。

E2Eの初回はsandboxにtagを指定したため、既存の不変ID検証で収集時に停止した。
実測したsha256 IDへ修正して再実行し、製品の制限は緩和していない。
全問題回帰・全Docker検査は未実施。sandbox・judge・問題dataは不変のため、
今回のローカル検証はfrontendと代表的な提出・画像・保存の経路に限定した。

commit・GitHub CI・本番反映は未実施。これはローカル修正候補の限定検証記録であり、
他の既知指摘やhost全体の更新完了を意味しない。PoC・攻撃試験・公開サイトへの提出は行っていない。

### 2026-10-21のcertifi信頼ストア更新

3問題追加PR #173のhead `b181579a2f8ec9291de39678f3bd87569a8efd84`に対する
[Supply Chain CI 39597198476](https://github.com/YusukeKato/ShellgeiOnlineJudge/actions/runs/39597198476)で、
sourceのcertifi 2026.7.22にCriticalのGHSA-6q48-6c7w-9gw2を1件検出し、公開を停止した。
DBは2026-10-21 06:31:02 UTC作成、Grype v0.119.0。
同runではrunnerも停止対象1件、他4 imageは停止対象0件だったが、非停止の検出は残る。
問題追加による依存変更はなく、新しいDBで既存のlockを照合した結果である。

[公式advisory](https://github.com/advisories/GHSA-6q48-6c7w-9gw2)と
[公式release](https://github.com/certifi/python-certifi/releases/tag/2026.10.19)に従い、
certifiだけを修正版へ更新した。取得hashとversionは[lock](../../poetry.lock)を正本とする。
Poetry 2.5.1で再生成し、他packageの定義・lock metadataが不変であることと、
PyPI公開hashとの一致、実際に読み込むCA bundleからemSign ECC Root CA - G3が除かれたことを確認した。

指摘は、侵害された中間CA鍵を持つ攻撃者が通信経路にも介在し、旧certifi bundleを信頼する
TLS clientへ偽の証明書を提示する場合のもの。lockではDocker SDK→requests経由のrunner依存である。
既定のdaemon接続は明示したrootless Unix socketで、提出sandboxはnetwork=noneのまま。
通常の提出から外向きHTTPS検証へ到達する経路や実際の侵害は確認していない。
package収録と悪用の成立を同一視せず、信頼ストアの更新とrunner imageの再buildで是正する。
host OS・外側proxy・他の信頼ストアまで更新済みとは扱わない。

TLS検証・sandbox制限・scanの停止条件を緩めず、例外登録も追加しない。
基本検査、新問のrootless検証、対象headのsource/runtime scan・全問題回帰・ブラウザ・配備確認を
完了条件とし、CIまたは本番確認が失敗した場合は公開を止める。
最終head・CI・本番結果は[PR #173](https://github.com/YusukeKato/ShellgeiOnlineJudge/pull/173)を参照する。

### 2026-10-19のfrontend nginx・X11/XPM更新

`6fd8ffcfbd867524f5ea29e37bde2a971fefebf2`の配備済みfrontend SBOMを、
2026-10-19 06:39:15 UTC作成のGrype DBで再照合し、libx11の修正可能なHighを1件確認した。
[X.Orgの公開情報](https://www.x.org/Development/Security/)とvendor情報に従い、
libx11を1.8.14-r0、libxpmを3.5.20-r0へ固定更新した。
対象はCVE-2026-88806、94283、94284、94285、94287。
通常のHTTP処理からX server応答・XPM解析へ到達する経路は未確認であり、
packageの収録と直接悪用の成立を同一視しない。
sandbox側のlibx11-6は`2:1.8.7-1ubuntu0.1`で、
[Ubuntu USN-8913-1](https://ubuntu.com/security/notices/USN-8913-1)の4 CVEの修正済みversionに一致する。
上流version番号だけで未修正と判断せず、vendorのbackportと区別した。libxpmは他の4 imageのSBOMでは確認されなかった。

[nginx公式advisory](https://nginx.org/en/security_advisories.html)の
CVE-2026-15176、93479、95101、97629、97205に対し、公式nginx 1.31.7 Alpine imageへdigest固定で更新した。
共有TLS session cacheを使う本構成は97629の条件に該当する。一方、mTLS、HTTP/3、
alias/rewrite・map regex・SSI/AIOの利用はリポジトリ設定では確認していない。
既存の明示的なOS library修正、TLS検証、proxy・API・sandbox制限は維持する。
固定値の正本は`frontend/Dockerfile`とし、nginx単体testも同じbaseを読み取る。

Grype v0.119.0とSyft v1.52.0は`ci/tools.json`のarchive SHA-256を検証して使用した。
同じDBによる更新後のローカルfrontend scanは72 packages / findings 3、
`blocking_before_exceptions`・`exceptions`・`risk_acceptances`・`blocking`はいずれも0。
対象X11/XPMの5 CVEは再検出されず、実imageのnginx・libx11・libxpmが上記修正版であることを確認した。
nginxはscannerで検出されなかったため、scannerだけを更新要否・修正完了の根拠にせず、
実binary/packageのversion下限をruntime回帰testへ追加した。
残る3件はBusyBox系packageのCVE-2025-60876（Medium、vendor修正版未提示）であり、
停止対象0を全脆弱性0とは扱わない。PoC・攻撃試験は行っていない。
ローカルではlock一致の専用Linux環境でRuff・mypy・非Docker 1,013件、frontendの基本検査と81件、
明示したrootless daemonでnginx受付・runtime・全125問の日英画面と提出保存を含む12件が成功した。
Windows作業コピーの改行差や検証用コピーのGit/import情報不足による初期の検査失敗は、
LF形式・Git情報を持つ専用cloneと明示したimport経路で解消した。製品側の制限は緩和していない。
CI・配備完了は、この記録だけで判断せず対象head/mainの実行結果と照合する。

### 2026-10-11のGo標準library更新

通常68の[PR #142](https://github.com/YusukeKato/ShellgeiOnlineJudge/pull/142)で、
[Supply Chain CI](https://github.com/YusukeKato/ShellgeiOnlineJudge/actions/runs/38110477084)が停止した。
DBの`/usr/local/bin/gosu`とsandboxの`/usr/local/bin/textimg`に静的linkされた
Go 1.26.8の標準libraryに、各10件の修正可能なHigh/Criticalが検出された。
対象IDはGO-2026-6603、6604、6605、6607、6608、6609、6610、6611、6612、6613。
backend・runner・frontendの停止対象は0件だったが、非ブロックの検出は残る。

[公式リリース](https://go.dev/doc/devel/release#go1.26.9)とCIの修正版情報を照合し、
gosu・textimgのbuild用stageだけをGo 1.26.9の公式imageへdigest固定で更新した。
gosu source・textimgのmodule lock、実行用OS、PostgreSQLのentrypoint・PGDATA、
sandboxの隔離・制限、スキャンの停止基準・例外policyは維持する。
修正版imageでrootless統合38件が成功した（362.46秒）。DBの更新・rollback、textimgの日本語・画像出力、
GIF、通常68、全117問の参照解答・判定・DB保存、実ブラウザ22提出を含む。
初回の問題追加時の全121件一括検査とは区別する。
同一headの全CI成功を確認するまでマージ・本番配備は停止する。

### 2026-10-07の統合候補とGitHub CI

2026-10-07 16:07:22 UTCまでに、統合commit
[`e52b19b`](https://github.com/YusukeKato/ShellgeiOnlineJudge/commit/e52b19b780fef0af5a5676c4613707e6127eae7e)の
[FastAPI CI](https://github.com/YusukeKato/ShellgeiOnlineJudge/actions/runs/37648101019)、
[React CI](https://github.com/YusukeKato/ShellgeiOnlineJudge/actions/runs/37648101003)、
[Supply Chain CI](https://github.com/YusukeKato/ShellgeiOnlineJudge/actions/runs/37648101067)が成功しました。
Python 3.12 / 3.13 / 3.14各839件・mypy 131 files、React 70件、policy等61件、
manifestの全115問のCompose提出・DB保存を含むrootless 26件を確認しています。

ローカルでは、既存の正規Linux環境でRuff・mypyと非Docker 839件、frontend 70件とbuild、
今回buildしたimageでrootless統合29件が成功しました。
新3問の別解・誤答を含む20コマンドと、日英それぞれの1440px / 320pxの12画面・DB保存12件も確認しました。
このローカル検証をGitHubの26件と区別します。Windowsで拒否されたDLLは使用せず、OS設定も変更していません。
実機iOS / Androidは未検証です。

GitHubの認証済み完了jobログで、sourceは322 packages / findings 0、runtime findingsは
backend 178 / runner 178 / frontend 35 / db 30 / sandbox 775でした。
全対象の`blocking_before_exceptions`・`exceptions`・`risk_acceptances`・`blocking`は0です。
停止対象0は全脆弱性0を意味しません。残存指摘はraw reportに保持し、例外追加・期限延長は行っていません。

source artifact `11494918848`はZIPと内部4 JSONのhash、cleanな`e52b19b`のbuild recordを照合済みです。
runtime artifact `11495851863`は完了jobログとmetadataで確認し、archive本文・image ID・report hashの独立照合は未実施です。
feature branchのprovenanceは設計どおりskipされました。main取込み後の同一SHAのCI・署名・配備確認とは別の結果です。

### 2026-10-07の統合前候補の検証結果

remote main `dd3bddb`の専用cloneで、source-map-jsを`1.2.2`、backend/runnerのPython baseを
`3.12.15-slim-trixie@sha256:e2e1e343308c173790faed72f2b2592fb201619fcde30af505883ded3f474ea5`へ更新しました。
source-map-jsは既存`^1.2.1`制約と他のlock entryを維持しています。
`GHSA-68fv-2mgg-jv7q` / `CVE-2026-93749`は同じsource脆弱性の別IDです。

2026-10-07 11:42 UTCの追加更新承認に基づき、backend/runnerの`libpcre2-8-0=10.46-1~deb13u3`、
frontendの`pcre2=10.49-r0` / `zlib=1.3.2-r1`、DBの`zlib=1.3.2-r1`を限定更新しました。
sandboxは既存Dockerfileをno-cacheでfresh buildし、既存`apt upgrade`で
`libssl3t64=3.0.13-0ubuntu3.16`を含む9 OS packageが更新されました。sandboxのソース・境界設定は変更していません。

全5製品と検証用browserを固有tagでbuildし、scanと回帰にimmutable IDを指定しました。
実package版・SBOM版・source commit・対象ID・raw report hashの対応を照合しています。
実backendのPythonは3.12.15、Expatは2.8.5です。frontend/DBはAlpine 3.24.2で、
apk repositoriesは公式`https://dl-cdn.alpinelinux.org/alpine/v3.24/main`と`community`でした。

Syft 1.52.0 / Grype 0.119.0、同じDB built `2026-10-07T06:31:48Z`での比較:

| target | OS追加更新前 全match / 停止 | 更新後 全match / 停止 | 例外/受容 |
| --- | ---: | ---: | ---: |
| source locks (322 packages) | 0 / 0 | 0 / 0 | 0 |
| backend (120 packages) | 179 / 1 | 178 / 0 | 0 |
| runner (121 packages) | 179 / 1 | 178 / 0 | 0 |
| frontend (71 packages) | 37 / 2 | 35 / 0 | 0 |
| db (50 packages) | 31 / 1 | 30 / 0 | 0 |
| sandbox (155 packages) | 823 / 1 | 775 / 0 | 0 |

source/runtime scanとも終了code 0です。修正版のあるHigh/Criticalの停止対象6 matches / 3 CVE
（CVE-2026-103111、CVE-2026-85091、CVE-2026-84782）は追加更新で0になりました。
原報告には非ブロックのHigh/Critical指摘128 matches / 20 IDが残ります。
fix stateはwont-fix 102、not-fixed 8、unknown 16、空状態2で、修正版の報告はありません。
Medium/Low等もraw reportに保持しています。これらを一括誤検知・安全として扱わず、追加更新・除外・受容は行っていません。
Debian PCRE2のvendor backportは[公式tracker](https://security-tracker.debian.org/tracker/CVE-2026-103111)で照合しています。

最終OS候補の検証:

- Ruff check/format、Linux non-Docker 833件成功。Docker 116件成功、失敗・skip 0。
- Compose/browser、DB role・migration・保存・旧image互換、runtime境界、sandbox制限、
  manifestの全112問を含みます。main候補の検証で、問題branchの追加62/63等との統合検証ではありません。
- frontend source/lockは前段から同一で、前段のformat/lint/typecheck、Vitest 70件、buildが成功。
  最終OS候補もDocker内typecheck/buildとbrowser回帰が成功しました。
- immutable IDs、raw Grype/Syft/CycloneDX、summary、runtime archive/hash、dirty build recordを保持。
  対象限定更新とsandboxのfresh buildによる全package差分も記録しています。

Windows mypyは正式な実行承認後もアプリケーション制御ポリシーでDLL読込を拒否され、未解決です。
この統合前候補の検証では、mypyと拒否DLLをLinux等の別経路で実行していません。
PR116の2.1.1案も別cloneの未検証案として分離しました。
当時は新除外・期限延長・OSセキュリティ設定変更、共有checkout変更、commit/push、PR変更、CI再実行、merge/deployを行っていません。
期限切れpolicyは非適用の監査記録のままです。その後の統合とGitHub CIは[上の確認結果](#2026-10-07の統合候補とgithub-ci)を参照してください。

[GitHub CI run 37605925305](https://github.com/YusukeKato/ShellgeiOnlineJudge/actions/runs/37605925305)は
問題branch `b54b66b`で、ログの停止matchはbackend14/runner14/frontend2/db1/sandbox0、source1でした。
Oct6 mainのfrontend1/db0は過去の値です。GitHub artifact転送はHTTP403で元JSON未取得のため、
元CIの個別IDとの前後比較は未完了です。上の比較は今回の専用候補のraw report同士によります。
Windows通常file補助scanのOpenSSL13件も、元CIの13件と同一視・一括除外していません。
以下の9月記録は過去の検証です。

### 2026-09-30: frontend libexpatの是正

`eb386f0`のclean worktreeに対応するbuild recordと、2026-09-29T16:57:28Zの
Grype 0.119.0によるfrontend検査reportを照合しました。Alpine 3.24の
`libexpat 2.8.4-r0`に`CVE-2026-93990`（High、CVSS 4.0 8.7）が1件あります。
対象は71 packages、全検出10件、停止対象1件、例外適用0件です。
[Alpine公式security DB](https://secdb.alpinelinux.org/v3.24/main.json)は修正版を
`2.8.5-r0`としています。[公式package情報](https://pkgs.alpinelinux.org/package/v3.24/main/x86_64/libexpat)
でも同じbranchのpackageと`libexpat.so.1`の提供を確認しました。

依頼者の実装承認に基づき、`frontend/Dockerfile`の既存nginx digestとlibuuid固定更新を維持し、
`libexpat=2.8.5-r0`の限定更新を追加しました。frontendだけの停止対象でもruntime scanを失敗させる
既存policy testのcaseを追加しています。Pythonの期限付き例外・リスク受容は変更していません。

この変更はreview前のworktree差分です。`test_supply_chain.py`、`test_runtime_image_pins.py`、
`test_nginx_config.py`の関連する非Docker検査26件と`git diff --check`が成功しました。
同じSyft・Grypeと更新済みDB（2026-09-30T06:32:47Z build）で全5 imageを検査し、
既存policy適用後の停止対象はすべて0件です。

| 対象 | packages | 全検出 | 誤検出例外 | リスク受容 | 適用後の停止対象 |
| --- | ---: | ---: | ---: | ---: | ---: |
| backend | 120 | 215 | 0 | 1 | 0 |
| runner | 121 | 215 | 0 | 1 | 0 |
| frontend | 71 | 9 | 0 | 0 | 0 |
| db | 50 | 5 | 0 | 0 | 0 |
| sandbox | 155 | 792 | 0 | 0 | 0 |

更新frontendの実packageは`libexpat 2.8.5-r0`で、`CVE-2026-93990`の検出は0件です。
残る9件（High 3件、Medium 6件）はscannerの修正版情報が未設定で、既存policyの停止対象外です。
raw reportから除外していません。backend・runnerは各1件の既存Pythonリスク受容を維持しており、
この成功をPython脆弱性の是正完了とは扱いません。

- Linux LF検証copyでRuff check・format（150 files）、mypy（127 files）、非Docker test計833件が成功。
  Windows checkoutの既存shell scriptのCRLFによる失敗はLF copyで解消し、Git metadataが必要な7件は
  process限定で元repositoryを参照して再検証しました。
- frontendのformat・lint・typecheck・buildとVitest 70件が成功。
- 今回buildした全imageを使うrootless統合16件が成功。Compose E2E 6件、runtime image 9件、
  新問の実行検証1件を含み、browser・DB保存・DB/runner停止復帰と全112問の参照解答を確認しました。

更新frontendのimmutable IDは`sha256:8e82432a251ae8c41828d6c5dcc4e2b478c70adc2289f124c24b089fc3223930`です。
今回のworkspaceの`validation/runtime-scan/`へ全検出report、SBOM、`runtime.tar`と`build-record.json`を保存しました。
build recordは`eb386f0`・未commit差分ありとして、全5 image IDと各fileのSHA-256を記録しています。
LF検証copyの対応は`validation/snapshot-record.json`、統合結果は`validation/integration-results.xml`に保存しました。
GitHub CIの再実行、本番配備、commitは行っていません。
下記9月20日の検査記録と今回の結果を区別し、SOJ-022全体は未解決のままとします。

### 2026-09-20の再スキャン記録

2026-09-20、`bcacb77`から依存・検証tool・互換性を維持したimageを一括更新したworktreeを検査しました。
固定済みSyft 1.52.0・Grype 0.119.0と当日取得した同一DBを使用し、全5 imageを再buildしました。
対象はpackageと脆弱性の組合せ数です。

| 対象 | リスク受容を適用する前の停止対象 |
| --- | ---: |
| Python / frontend lock file | 0 |
| backend image | 1 |
| runner image | 1 |
| frontend image | 0 |
| DB image | 0 |
| sandbox image | 0 |

lock fileでは停止対象以外も含めて検出0件でした。imageの停止対象0は全脆弱性0を意味せず、
低severity・未修正等の検出はreportに残しています。
既に是正したAnyIO・OS libraryの停止対象は再導入されていません。
backend・runnerの実Python 3.12.14／Expat 2.8.3と対応Pythonの範囲・runtime境界を維持し、
追加修正までの[一時許容と撤去条件](#soj-022の一時許容と撤去条件)を定めています。

残る各1件はPython標準libraryの`CVE-2026-82049`（High）です。
tarfileの`data`／`tar` filterが、symlinkへのhard linkを使うarchiveで展開先外への影響を防げない問題です。
[公式issue](https://github.com/python/cpython/issues/157190)と
[3.12向け修正PR](https://github.com/python/cpython/pull/157454)を確認しましたが、同日の先行調査時点ではPRが未mergeで、
採用可能な公式3.12修正版はありません。Grypeは3.14.0b1以降を修正版と判定します。
公式3.14.7 imageも実測しましたが、内蔵Expatが2.8.2へ後退し、
[2.8.3の修正](https://github.com/python/cpython/issues/155558)を維持する既存runtime testに失敗するため採用しません。
公式修正版の公開後、PythonとExpatの両条件を満たすimageで再build・scan・統合testを行ってください。

GitHub上でも`3d4114a`の[Supply Chain CI](https://github.com/YusukeKato/ShellgeiOnlineJudge/actions/runs/35507570995)で
同じCVEをbackend・runnerから各1件検出しました。Python・React・source jobは成功していますが、
runtime scanが終了code 2で停止したため、後続のE2Eと署名登録は実行されていません。
[Production deploy](https://github.com/YusukeKato/ShellgeiOnlineJudge/actions/runs/35507570991)も
同じcommitのCI成功待ちで停止し、AWS認証・SSH配備は実行されていません。
`8fb15e7`の[Supply Chain CI](https://github.com/YusukeKato/ShellgeiOnlineJudge/actions/runs/35514463599)でも
runtime scanが失敗し、[Production deploy](https://github.com/YusukeKato/ShellgeiOnlineJudge/actions/runs/35514463622)は
CI成功待ちで停止しました。認証Actionの更新では解消せず、Python修正または下記の明示的なリスク受容が必要です。

現行のbackend・runnerに利用者提供tarの展開処理はありません。
runnerの`execution_archive.py`は通常fileのtarを作成し、展開はsandbox内の別処理です。
この到達性を評価し、下記の未修正リスク受容を別policyとして追加します。
既存の修正済みPython例外のCVE・期限・hashは変更しません。今回のDBでは既存3件は停止対象外で、誤検出例外適用は0件です。
更新imageの一部binary hashは旧policyと異なるため、将来再検出されても旧policyで自動的に通過させません。

一括更新時の検証（リスク受容を適用する前）:

- lock整合性、ruff・format・mypy、非Docker 793件がPython 3.12・3.13・3.14で成功。
- 更新した全imageを使うrootless統合26件がすべて成功（skipなし）。
  実runtime境界、Compose経由の全111問・DB保存、browser表示、認証・revision拒否、
  DB・runner停止復帰、配備時のDB保持とmigration失敗時の受付停止、PostgreSQL更新・復帰互換性、
  sandboxの収録command・画像生成を確認しました。
- Goの不要checksum整理後もsandboxを再buildし、textimg binaryの一致、sandbox統合8件とscanを再確認しました。
- 同一DBでlockと全5 imageをscanし、実scannerの合成secret・脆弱package・破損SBOM検査も成功。
  上表の残存検出によりruntime scan全体は不合格です。
- frontendのformat・lint・typecheck・68 test・buildが成功。

検査reportと対象のimmutable IDはlocalの`.soj-deploy/batch-review/`に保存しています。

## SOJ-022の一時許容と撤去条件

統合候補`e52b19b`では例外・リスク受容の適用は0です。
旧リスク受容policyは2026-10-04、旧Python誤検出例外は2026-10-05に失効し、非適用の監査記録として残っています。
policy・専用処理の撤去は未実施です。以下は2026-09-20当時の承認条件と検証履歴であり、現在の許容を与えるものではありません。

2026-09-20、依頼者は自動デプロイ復旧のため、現行コードで影響が限定的であることを条件に
未修正リスクの一時許容を指示しました。CVEの修正完了・誤検出とは扱わず、SOJ-022は未解決のままです。
対象・期限・承認主体・実装hash・撤回条件は
[`ci/python-runtime-risk-acceptance.json`](../../ci/python-runtime-risk-acceptance.json)を正本とします。
適用・失効時の挙動は[CIのリスク受容](../CI.md#未修正python脆弱性の一時的なリスク受容)を参照してください。

影響評価の根拠:

- 本番APIはcommandとproblem IDを受け取り、認証付きrunnerへ渡し、結果を判定してDBへ保存します。
  利用者提供tarをbackend・runnerのPythonで展開する処理はありません。
- `backend/soj_runner/execution_archive.py`は通常fileだけのtarを生成します。
  command本文でtarのentry種別やlink先を指定することはできず、展開はsandbox内の別処理です。
- CI toolのinstallerは固定hashを検証し、通常fileのみ`extractfile`で取得します。
  browser E2Eには専用browser containerが作った画像archiveの`extractall(filter="data")`がありますが、
  本番backend・runnerの処理ではなく、この許容をCI実行環境全体へ適用するものではありません。
- 上記は現行の利用経路に基づく評価であり、依存全体の未知の経路や将来の変更まで安全と保証しません。
  信頼できないarchiveのPython展開を導入する場合、または悪用経路が判明した場合は直ちに再評価・撤回します。

2026-09-20当時に定めた撤去条件（担当: リポジトリ保守者）:

1. 上記のCPython issue・3.12向けPRと公式imageを再確認する。
2. Pythonのtarfile修正と既存Expat修正を両立するimageをdigest固定で採用する。
   公式版が間に合わない場合は修正の先行適用を検討する。期限だけを自動延長しない。
3. 全5 imageのscan、rootless統合・全問題回帰を実行し、許容なしで対象CVEが停止しないことを確認する。
   修正済み実装への誤検出が残る場合は、修正根拠を確認して別途レビューする。
4. このリスク受容policyと専用処理・testを撤去し、GitHubの同じcommitでCI・署名・本番自動更新を確認する。

一時許容の検証（2026-09-20）:

- Python 3.14でruff・format・mypy、非Docker test 831件が成功。
  失効日当日、別CVE・製品・package・path、実装hash不一致、probe障害を許容しないことを確認しました。
- 更新確認した脆弱性DBと実rootless imageを使い、全5 imageのscanが成功。
  backend・runnerのraw検出は各170件のまま保持し、各1件だけをリスク受容へ分類、適用後の停止対象は全製品0件です。
  実装は未修正のままです。policyと評価記録を含むbuild recordも生成しました。
- アプリ・依存・imageの変更はなく、検証済みimageを再利用しました。今回のE2E・全問題回帰は再実行していません。
  localの検証記録は`.soj-deploy/risk-review/`に保存しています。

当時、依頼者から`aabdd58`の自動デプロイ成功・本番更新完了の報告を受けました。
当時の一時許容を含む本番反映は、脆弱性の修正完了を意味しませんでした。
現在の更新・検証結果は[統合候補の確認](#2026-10-07の統合候補とgithub-ci)、
再検査の手順は[CI文書](../CI.md#ローカルでの検証)を参照してください。

## SOJ-022：依存・imageの是正記録

2026-09-05、依頼者の次の対策実装依頼に対し、CIを停止させるP1課題を優先しました。
アプリ依存・nginxの是正は依頼者のreview承認後、`cb044c7`でcommit済みです。
派生DBの是正は依頼者のreview承認後、`6b59c19`でcommit済みです。
Pythonの期限付き例外は依頼者のreview承認後、`4120a76`でcommit済みです。
期限付きで扱うPythonのscanner判定と実CI・本番確認が残るため、
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
この表は独自sandbox導入前の検証記録です。今回の比較は下記「独自sandboxの是正」を参照してください。
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
当時のimage側は残存検出によりCIを停止しました。低severity・未修正の検出を含め、全脆弱性がなくなったという意味ではありません。

### Python判定と内蔵Expatの検査

2026-09-05に検出したbackend・runnerの各3件はPythonの公式修正情報とNVDのversion範囲の不一致でした。
例外の対象・根拠・期限・実装hashは[`ci/python-runtime-exceptions.json`](../../ci/python-runtime-exceptions.json)、
適用条件と失効時の挙動は[CIの期限付き例外](../CI.md#python-runtimeの期限付き例外)を正本とします。
この例外policyは当時の固定image専用です。現在の検出・適用状況は[現在の停止対象](#soj-022の現在の停止対象)を参照してください。
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

- 2026-09-05に検出したbackend・runnerの各3件は`CVE-2026-3644`、`CVE-2026-4224`、`CVE-2026-7210`です。
  [Python 3.12.14の公式修正情報](https://www.python.org/downloads/release/python-31214/)と、
  [Expat修正条件を含む公式リリース説明](https://blog.python.org/2026/08/python-31214-31116-31021/)を確認しました。
  当時の実imageはPython 3.12.14／Expat 2.8.3であり、修正済みversionに対するscanner判定の不一致でした。
  期限付き例外で区別した当時の結果は、NVD側の判定が訂正されたことを意味しません。
  期限前に再評価し、DB側で不一致が解消した場合は例外を削除してください。
- 低severity・未修正の検出は引き続きreportに残します。sandboxで実行できる任意コードと
  host kernelの境界は、scannerの成功だけで安全性を保証できません。
- GitHub上のCI、署名・required checks、本番promotionは未実施です。

### 独自sandboxの是正

依頼者の方針に従い、ShellgeiBotImageの全toolを保守する方式から、公式Ubuntuをbaseとする
独自imageへ切り替えました。現在の全92問とrunnerが必要とするpackage、ShellGeiData、
依頼者指定のtextimgと日本語fontを収録します。Go compilerはtextimgのbuild用stageだけで使用し、
依存lockもtextimg専用の1組に限定しています。
構成・互換性の正本は[sandbox文書](../../deploy/sandbox/README.md)、
ID設定と更新手順は[本番運用](../PRODUCTION.md#sandbox専用image)を参照してください。

- base digestを固定。ShellGeiDataはbuild時の最新commit全体を収録し、そのrevisionを記録。
  Ubuntuの署名済みrepositoryで更新を適用し、
  完成したimageをimmutable IDでscan・実行・archiveに使用します。
- 実行用imageに不要な言語・開発環境、sudo・ping等を導入せず、setuid/setgid属性を除去。
  ImageMagickのdelegate・format・resourceも制限します。Docker側の既存制限は維持しています。
- `SANDBOX_IMAGE_ID`は必須で、旧imageへのfallbackはありません。
  CIは独自sandboxもbuild・scan・archiveに含め、同じIDを実行テストへ渡します。
- frontend・DBで再現した各4件のlibuuid検出への固定更新も、同じ是正commitに含めています。
  source packageのutil-linuxに由来するscanner分類であり、個別serviceからの悪用可能性とは区別します。
- 新しい検出除外や例外、停止条件の緩和は追加していません。

同じ固定scanner・2026-09-05取得DBでの停止対象match数:

| 対象 | 是正前 | 独自sandbox導入後 |
| --- | ---: | ---: |
| sandbox | 248 | 0 |
| frontend | 4 | 0 |
| 派生DB | 4 | 0 |
| backend / runner | 各3（既存例外後0） | 各3（既存例外後0） |

独自sandboxのinventoryは155 package、全検出は729 matchです。High/Criticalはなく、
Medium以下の未修正・wont-fix検出をraw reportへ残しています。
全脆弱性の解消や、ホストkernelを含む安全性を保証する結果ではありません。
imageはDocker inspectのSizeで630,300,114 bytes。ShellGeiDataの収録・更新仕様は上記の正本を参照してください。

今回の検証:

- 新しい不要コマンドの不在testが旧imageのGoを検出してREDとなることを確認。
  初回の独自imageではJPGの別名がpolicyに不足し、画像問題が失敗。許可を修正し、
  正解画像・問題data・judgeを変更せず回帰確認しています。
- ruff・format・mypy、非Docker 645件が成功。mypyでは作業用`backend_data*`
  （venv・取得物）だけを除外し、対象source 104 fileを検査。
- frontend基本5検査・35件、source scan・scanner fixtureの成功結果は直前の同じ差分の検証から維持。
  今回はfrontendのcode・依存・imageを追加変更していません。
- 独自sandboxを指定したrootless Docker 31件がすべて成功。Compose・直接sandbox両経路の全92問、
  browser、認証・revision拒否、DB・runnerの停止復帰、隔離・資源制限と必要コマンド・画像policyを含む。
- ShellGeiDataの追加directory・revision記録のtestは旧imageでRED、新imageで成功。
  上流の最新HEADと記録revisionが一致し、全788 entryのpath・file内容・symlinkをarchiveと照合。
  cacheありの再buildでもGitの最新HEADを再確認することをログで確認した。
- textimgの追加testは未収録imageでRED、追加後は日本語・ANSI色・PNG pipe・JPEG/GIF保存が成功。
  日本語画像を目視確認し、Go compiler不在と既存の隔離・画像policyも確認した。
- 最終5 imageを同じDBでscanし、検査したIDのarchiveとbuild recordを再生成。
  archiveのOCI indexと全image IDの一致、recordのfile hashを確認した。
- 独自sandbox・libuuidの是正はreview承認後に`34a9041`でcommit済みです。
  GitHub上のworkflow・署名と本番反映は未確認です。
