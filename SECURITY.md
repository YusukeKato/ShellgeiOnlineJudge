# セキュリティモデルと制約

ShellgeiOnlineJudgeは、インターネット経由で入力された任意のシェルコマンドを
sandboxコンテナ内で実行するサービスです。

基本方針は次のとおりです。

- 利用者の意図にかかわらず、外部入力には同じセキュリティ制御を適用する
- 外部入力をセキュリティ境界の外側にあるデータとして扱う
- Dockerコンテナやrootless Dockerだけを完全なセキュリティ境界とみなさない

## 実行経路

```text
frontend（nginx）
    -> backend（FastAPI）
        -> rootless Docker socket
            -> sandboxコンテナ
        -> PostgreSQL
```

backendはrootless Docker daemonを操作する権限を持ちます。
sandboxコンテナにはDocker socketをマウントしません。

## sandboxコンテナの設定

1つのbackendプロセスは、起動時に3個のsandboxコンテナを準備します。
管理対象数の上限も3個です。

管理対象には次のコンテナを含みます。

- poolで待機しているコンテナ
- コマンドを実行しているコンテナ
- 削除に失敗したコンテナ

削除に失敗した場合は実行可能数を減らし、上限を超える代替コンテナを生成しません。

sandboxコンテナには次の設定を適用します。

- rootless Docker daemon上で実行
- `network_mode=none`
- `ipc_mode=none`
- メモリ512 MiB
- memory swap合計512 MiB
- CPU 0.5 core
- PID上限50
- 全Linux capabilityをdrop
- `no-new-privileges`
- `/media`を100 MiBのtmpfsとしてmount
- file size ulimitを50 MBに設定
- 管理用label `com.shellgei-online-judge.sandbox=true`

sandbox内のコマンドはコンテナ内rootとして動きます。

次の制御は設定していません。

- read-only root filesystem
- 独自のseccomp policy
- 独自のAppArmor policy
- 独自のSELinux policy

rootless Dockerはcontainer escape時の影響を軽減しますが、
escapeを防ぐ保証にはなりません。

## 実行時間と同時実行数

シェルコマンドの既定実行時間は10秒です。
stdoutやstderrを出さない処理も独立したwatchdogの対象になり、期限到達時はコンテナを停止します。

1つのbackendプロセスが同時に実行するsandbox処理は最大3件です。

- 上限到達時のリクエストはqueueへ追加しない
- APIはbusy応答を返す
- asyncio timeout後もworker threadが動作している場合は実行枠を保持する
- worker threadの終了後に実行枠を解放する

これらの上限はbackendプロセス単位です。
複数workerまたは複数replicaでは上限が共有されず、プロセス数に応じて合計実行数とコンテナ数が増えます。

## stdout、stderr、画像

stdoutとstderrは結合されたstreamとして読み込みます。
backendメモリに保持する量は、APIが返す最大文字数の4倍までです。

上限超過時は次の処理を行います。

- コンテナを停止する
- 上限以降の出力を保持しない
- 画像を保持しない

出力画像は最大750,000 bytesです。
watchdogが有効な間に、次のいずれかをコンテナの書き込み可能layerへ退避します。

- `/media/output.gif`
- `/media/output.jpg`

退避量は最大750,001 bytesです。
コンテナ停止後に退避ファイルを読み、次の各段階で上限を検査します。

- Dockerが返すfile size metadata
- Docker archive全体の転送量
- archiveから展開した画像データ

上限超過または形式に不備があるarchiveは、画像なしの結果として扱います。

## リクエストごとのデータ分離

次のファイルは、リクエストごとのtar archiveとしてbackendメモリ上に生成します。

- ユーザーが入力したシェルスクリプト
- 問題の入力ファイル

リクエスト間で共有するホスト側一時ファイルは使用しません。
archiveは貸し出されたsandboxコンテナへ直接転送します。

problem IDには、ファイルパスへ使用する前に次の検証を適用します。

- 長さは1文字以上64文字以下
- ASCIIの英字、数字、区切りのハイフンだけを許可
- 先頭、末尾、連続するハイフンを許可しない
- path separator、ピリオド、underscore、空白、制御文字を許可しない

この検証は次の入力経路と内部処理へ適用します。

- shell実行APIのJSONに含まれる`problem_id`
- 問題取得APIのURL parameter
- sandboxへ問題入力を渡す処理
- 判定用YAMLと画像を読み込む処理

形式が正しくても登録されていないproblem IDは、
sandboxの取得やDB照会を開始する前に404で拒否します。

shell commandには次の検証を適用します。

- carriage returnを除去して改行を正規化
- 長さは1文字以上1,000文字以下
- NULを許可しない
- UTF-8としてencodeできない文字列を許可しない
- JSONに定義されていない追加fieldを許可しない

shell commandの改行、空白、記号、通常のUnicode文字は、
任意のshell commandを扱うサービス仕様として許可します。

## コンテナの終了処理

次の場合は、コンテナの停止・削除処理へ進みます。

- 正常終了
- 実行timeout
- 出力超過
- 実行準備失敗

FastAPIのgraceful shutdownでは、次の終了処理を行います。

- 管理対象コンテナの削除
- Docker clientのclose
- ThreadPoolExecutorのshutdown

次の場合はコンテナが残存する可能性があります。

- backendの`SIGKILL`または異常終了
- ホスト停止またはkernel障害
- Docker daemon停止・応答不能
- Docker APIによるkillまたはremoveの失敗

起動時に以前のbackendプロセスが残したコンテナをlabelから検出・回収する処理はありません。
残存コンテナ数と削除失敗をホスト側で監視する必要があります。

Docker clientのHTTP timeoutは15秒です。
これはdaemon障害時の長時間blockを軽減しますが、
すべてのDocker操作が必ず15秒以内に終了する保証ではありません。

実行threadの増加は次の上限でも抑制します。

- ThreadPoolExecutorのworker数
- sandbox実行slot数

## rootless Dockerの強制

Compose操作には`deploy/rootless-compose.sh`を使用します。
このwrapperは接続先daemonの`SecurityOptions`を検査します。

次の接続先は拒否します。

- rootful Docker daemon
- TCPのDocker endpoint

backendも起動時にDocker daemonの`SecurityOptions`を検査します。
`name=rootless`がなければ起動に失敗します。
開発環境と本番環境のどちらもrootless Dockerが必要です。

Docker build contextから次を除外します。

- `.env`
- TLS証明書と秘密鍵
- Git履歴
- Python・Node.jsのcacheと生成物

frontendのbuildへ渡す環境変数は、ブラウザへ公開される`REACT_APP_*`だけです。
`REACT_APP_*`へ秘密情報を設定してはいけません。

## Docker socketの権限

backendにはrootless Docker socketをmountします。
backendの実行権限が意図しない形で利用された場合、
rootless daemonの権限で次のリソースを操作できる状態になります。

- daemonが管理する全コンテナ
- Dockerイメージ
- Docker volumeとDBデータ
- Docker network
- daemonユーザーが読み書きできるホストファイル

同じdaemonで動作するDBとfrontendも同じ影響範囲に含まれます。
rootless socketはホストroot相当のrootful socketより権限が限定されます。
ただし、Web backendとDocker実行基盤の間の独立したセキュリティ境界にはなりません。

Web APIとDocker実行基盤を分離する場合に必要な構成は次のとおりです。

```text
Web API（Docker socketなし）
    -> 認証され、固定スキーマだけを受け付けるrunner API
        -> 専用Dockerホストまたは使い捨てVM
```

runner APIは、Web APIから次の値を受け付けてはいけません。

- イメージ名
- mount
- capability
- device
- privileged mode
- その他の任意のDocker option

汎用Docker socket proxyは独立したsandbox境界として扱いません。

## ネットワークとHTTPの制約

frontend nginxには、次の明示的な制限がありません。

- リクエスト頻度
- 同時接続数
- request body size
- proxy timeout

FastAPIは、JSONをparseした後のshell commandとproblem IDを検証します。
ただし、parse前のHTTP request body全体に対する上限にはなりません。

アプリケーションの実行slotだけでは、次の対象を十分に保護できません。

- frontend
- backend
- DB
- Docker daemon
- ホストOS

インターネット公開時は、外側の層で受付制御を行う必要があります。

- load balancer
- reverse proxy
- WAF
- firewall

proxy配下のクライアントIPを利用する場合は、
接続を許可するproxyと`X-Forwarded-For`の扱いを明示します。

## 依存関係とイメージの制約

sandboxイメージとbase imageはtagで参照しており、digestを固定していません。

次のsupply chain対策も構成されていません。

- SBOM生成
- 署名検証
- 継続的な脆弱性scan

イメージや依存関係を更新する場合は、次のテストが必要です。

- rootless Docker統合テスト
- 全問題回帰テスト

## 必要な追加対策

- sandbox内の非rootユーザー化
- read-only root filesystemと容量制限付き書き込み領域
- rootless環境で利用可能なseccomp・LSMによる追加制約
- nginxまたは外側proxyのrequest body・rate・connection・timeout制限
- 複数worker・複数hostで共有する受付制御
- 起動時の残存sandbox検出・回収
- 判定値の正規化と画像比較処理の修正
- イメージのdigest固定、SBOM、署名検証、脆弱性scan
- Web APIとrunnerの分離
