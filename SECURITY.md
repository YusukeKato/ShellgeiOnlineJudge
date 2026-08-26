# セキュリティモデルと制約

ShellgeiOnlineJudgeは、インターネット経由で入力された任意のシェルコマンドを
sandboxコンテナ内で実行するサービスです。
この文書は、現在のセキュリティ仕様と制限値の正本です。

現在の未解決課題、対応状況、優先順位は、
[セキュリティ課題と対応状況](./docs/security/README.md)を参照してください。

環境構築やテストは[開発環境](./docs/DEVELOPMENT.md)、
本番環境で必要な設定と運用確認は[本番運用](./docs/PRODUCTION.md)を参照してください。

基本方針は次のとおりです。

- 利用者の意図にかかわらず、外部入力には同じセキュリティ制御を適用する
- 外部入力をセキュリティ境界の外側にあるデータとして扱う
- Dockerコンテナやrootless Dockerだけを完全なセキュリティ境界とみなさない

## 実行経路

```text
frontend（nginx）
    -> backend（FastAPI）
        -> PostgreSQL
        -> 認証付きrunner API（内部network）
            -> rootless Docker socket
                -> sandboxコンテナ
```

backendにはDocker socketをmountしません。
Docker操作は、ホストへportを公開しないrunnerだけが行います。
sandboxコンテナにはDocker socketをマウントしません。

backendからrunnerへ送るfieldは次の2つだけです。

- shell command
- problem ID

runner APIは共有secretで認証し、イメージ名、mount、capability、device、
privileged modeなどのDocker optionを受け付けません。

## sandboxコンテナの設定

1つのrunnerプロセスは、起動時に3個のsandboxコンテナを準備します。
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
- root filesystemをread-onlyでmount
- `/work`を64 MiB、inode上限4,096のtmpfsとしてmount
- `/tmp`を32 MiB、inode上限4,096のtmpfsとしてmount
- `/media`を100 MiB、inode上限1,024のtmpfsとしてmount
- `/dev`を64 MiB、inode上限1,024のtmpfsとしてmount
- `/work`と`/tmp`は生成したscriptや一時実行ファイルとの互換性のため実行可能
- `/media`と`/dev`は`noexec`
- すべてのtmpfsは`nosuid,nodev`
- file size ulimitを50 MBに設定
- 1processあたりのfile descriptor上限を256に設定
- core dumpを無効化
- 管理用label `com.shellgei-online-judge.sandbox=true`

sandbox内のコマンドはコンテナ内rootとして動きます。

通常のcommandと問題入力は`/work`に配置します。
working directoryも`/work`です。
`HOME`は`/tmp/home`、`TMPDIR`は`/tmp`です。

既存の画像問題が使用する相対パス`media/output.jpg`は、
`/work/media`から`/media`へのsymlinkで維持します。
問題用の既存データを相対パスで参照するcommandのため、
`/work/ShellGeiData`からread-only root上の`/ShellGeiData`へのsymlinkも提供します。

任意の通常ファイルを書き込める場所は、上記4つのtmpfsに限定します。
tmpfsの容量合計は1コンテナあたり260 MiBで、使用量は512 MiBのmemory cgroupにも計上されます。
容量またはinode上限へ達した書き込みは、コンテナ内で`ENOSPC`になります。

次の制御は設定していません。

- 独自のseccomp policy
- 独自のAppArmor policy
- 独自のSELinux policy

rootless Dockerはcontainer escape時の影響を軽減しますが、
escapeを防ぐ保証にはなりません。

## 実行時間と同時実行数

シェルコマンドの既定実行時間は10秒です。
stdoutやstderrを出さない処理も独立したwatchdogの対象になり、期限到達時はコンテナを停止します。

1つのrunnerプロセスが同時に実行するsandbox処理は最大3件です。

- 上限到達時のリクエストはqueueへ追加しない
- APIはbusy応答を返す
- asyncio timeout後もworker threadが動作している場合は実行枠を保持する
- worker threadの終了後に実行枠を解放する

sandbox実行の開始頻度には、runnerプロセスごとに次の制限を適用します。

- 平均1件/秒
- 起動直後または未使用時の即時実行は最大3件
- lockで保護したtoken bucketを使用する
- tokenがないrequestはDB操作やDocker操作の前にbusy応答を返す

これらの上限はrunnerプロセス単位です。
複数workerまたは複数replicaでは上限が共有されず、プロセス数に応じて
合計実行数、コンテナ数、runnerの許容開始頻度が増えます。

## stdout、stderr、画像

stdoutとstderrは結合されたstreamとして読み込みます。
runnerメモリに保持する量は、APIが返す最大文字数の4倍までです。

上限超過時は次の処理を行います。

- コンテナを停止する
- 上限以降の出力を保持しない
- 画像を保持しない

出力画像は最大750,000 bytesです。
watchdogが有効な間に、次のいずれかを固定コマンドで読み取ります。

- `/media/output.gif`
- `/media/output.jpg`

読み取りにはread-only root filesystem上の`/usr/bin/head`を使用し、
最大750,001 bytesをDocker execのstreamとしてrunnerへ返します。

runnerも750,001 bytesを上限とするbufferへ読み込み、
750,000 bytesを超えた画像を破棄します。

画像をwritable root layerへ退避せず、Docker archive APIも使用しません。
上限超過または読み取り失敗は、画像なしの結果として扱います。

## リクエストごとのデータ分離

次のファイルは、リクエストごとのtar archiveとしてrunnerメモリ上に生成します。

- ユーザーが入力したシェルスクリプト
- 問題の入力ファイル

リクエスト間で共有するホスト側一時ファイルは使用しません。
archiveはrunnerでBase64へencodeし、Docker execの一時的な環境変数として渡します。
sandbox内の固定コマンドがBase64をdecodeし、read-only root filesystem上の
`base64`と`tar`を使用して`/work`へ展開します。
利用者の入力内容を展開コマンドへ連結しません。

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

runnerのgraceful shutdownでは、次の終了処理を行います。

- 新しいsandbox取得を停止
- 管理対象コンテナをkillして実行threadを解除
- ThreadPoolExecutorの終了を待機
- 管理対象コンテナを削除
- Docker clientをclose

sandboxには、次の管理情報を設定します。

- 一意なcontainer名
- sandboxを示すlabel
- デプロイ環境を示すowner label
- runner起動単位を示すinstance label

runner起動時は、同じowner labelを持つ既存sandboxをpool作成前に削除します。
一覧取得または削除に失敗した場合は、新しいpoolを作らずrunnerの起動に失敗します。
`SANDBOX_OWNER_ID`は、同じDocker daemonを使う環境ごとに異なる値を設定し、
1つのownerにつきrunnerは1 instanceだけ起動してください。

containerはcreateとstartを分け、create前に一意な名前を管理対象へ登録します。
create応答が失われた場合は名前からcontainerを再取得して削除します。
startまたはcgroup検証に失敗したcontainerも、poolへ追加せず削除します。
削除結果が確認できない名前またはcontainerは管理上限へ含め続けます。

次の場合はコンテナが残存する可能性があります。

- ホスト停止またはkernel障害
- Docker daemon停止・応答不能
- Docker APIによるkillまたはremoveの失敗
- runnerが異常終了した後、再起動が完了しない場合

Composeのrunnerは`restart: always`で再起動し、起動時回収を実行します。
ただし、Docker daemon側だけで強制するsandboxの有効期限はありません。
runner再起動、残存sandbox数、起動時回収失敗をホスト側で監視してください。

Docker clientのHTTP timeoutは15秒です。
これはdaemon障害時の長時間blockを軽減しますが、
すべてのDocker操作が必ず15秒以内に終了する保証ではありません。

実行threadの増加は次の上限でも抑制します。

- ThreadPoolExecutorのworker数
- sandbox実行slot数

## 実行ログとDockerログ

動的に生成するsandboxコンテナは、Docker logging driverを`none`に固定します。
sandboxの待機PID 1はstdin、stdout、stderrを`/dev/null`へ接続します。
利用者コマンドのstdoutとstderrはDocker execのstreamからだけ取得し、
backendへ返す出力量の上限を適用します。

この構成により、sandboxのPID 1を経由した出力をDocker container logへ
保存しません。

DBの実行ログは、次の両方を満たす範囲だけ保持します。

- 作成から365日以内
- 最新10,000件以内

保持期間と最大件数は、次の環境変数で変更できます。

- `EXECUTION_LOG_RETENTION_DAYS`
- `EXECUTION_LOG_MAX_ROWS`

どちらも1以上の整数が必要です。
不正な値が設定されている場合、backendは起動しません。

古いログは、backend起動時と新しい実行ログの保存時に削除します。
新しいログの保存と件数による削除は、同じDB transaction内で処理します。

Composeで起動するDB、runner、backend、frontendのDockerログには、
すべて`local` logging driverを使用します。
各serviceのログは10 MiB、3ファイルまでにrotationします。

これらは、ExecutionLogとDocker container logの無期限な累積を防ぐ制御です。
PostgreSQL volume全体のfilesystem quotaにはなりません。
DB volumeは専用filesystemまたはquotaで制限し、容量を監視してください。

## rootless Dockerの強制

Compose操作には`deploy/rootless-compose.sh`を使用します。
このwrapperは接続先daemonの`SecurityOptions`を検査します。

次の接続先は拒否します。

- rootful Docker daemon
- TCPのDocker endpoint

runnerも起動時にDocker daemonの`SecurityOptions`を検査します。
`name=rootless`がなければ起動に失敗します。
同時にcgroup v2とsystemd cgroup driverを必須とし、作成した各sandbox内で
メモリ512 MiB、PID数50、CPU 0.5 coreの実値を検査します。
いずれかの制限が反映されていないsandboxは直ちに破棄し、
初期poolを満たせない場合はrunnerの起動に失敗します。
開発環境と本番環境のどちらもrootless Dockerが必要です。

Docker build contextから次を除外します。

- `.env`
- TLS証明書と秘密鍵
- Git履歴
- Python・Node.jsのcacheと生成物

frontendのbuildへ渡す環境変数は、ブラウザへ公開される`REACT_APP_*`だけです。
`REACT_APP_*`へ秘密情報を設定してはいけません。

## runnerとDocker socketの権限

rootless Docker socketは、外部HTTP requestを処理しないrunnerだけにmountします。
backendとrunnerは専用の内部Docker networkで接続し、runnerのportはホスト、
frontend、DBへ公開しません。
backendのrunner HTTP clientはproxyを明示的に無効化し、
`HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`等の環境変数を使用しません。

runner APIの共有secretは32文字以上の安全なランダム値を使用します。
runnerは認証、入力schema、登録済みproblem ID、開始頻度、同時実行数を検査してから
sandbox処理を開始します。

runnerの実行権限が意図しない形で利用された場合、
rootless daemonの権限で次のリソースを操作できる状態になります。

- daemonが管理する全コンテナ
- Dockerイメージ
- Docker volumeとDBデータ
- Docker network
- daemonユーザーが読み書きできるホストファイル

同じdaemonで動作するDB、backend、frontendも同じ影響範囲に含まれます。
rootless socketはホストroot相当のrootful socketより権限が限定されます。
Web backendが意図しない動作をした場合でも、任意のDocker APIを直接操作できず、
固定schemaのrunner APIを通じた制限付きsandbox実行だけが可能です。

Compose構成より影響範囲を小さくする場合は、runnerを専用Docker hostまたは
使い捨てVMへ配置します。

```text
Web API（Docker socketなし）
    -> 認証され、固定schemaだけを受け付けるrunner API
        -> 専用Dockerホストまたは使い捨てVM
```

現在のrunner APIは、Web APIから次の値を受け付けません。

- イメージ名
- mount
- capability
- device
- privileged mode
- その他の任意のDocker option

汎用Docker socket proxyは独立したsandbox境界として扱いません。

## ネットワークとHTTPの制約

frontend nginxは、すべてのrequest bodyを16 KiB以下に制限します。
FastAPIへ転送する前にrequest body全体をbufferingします。

Compose内のfrontend nginxは、IP addressをkeyとするrate limitと
connection limitを適用しません。
rootless Dockerのport forwardingやホスト側reverse proxyを経由すると、
frontend nginxから見た送信元が中間componentへ集約されるためです。
ここでIP単位の共有枠を適用すると、不正JSONや未登録problemなどの
sandboxを起動しないrequestも、正常requestと同じ枠を消費します。

Docker開始頻度の正本はrunnerのtoken bucketです。
runnerは認証、JSON schema、problem ID、登録済みproblemを検証した後に、
平均1件/秒、burst 3の開始制限を適用します。
同時sandbox実行数は3件のままです。

接続とproxyには次のtimeoutを適用します。

- client request header受信: 10秒
- client request body受信: 10秒
- keep-alive: 15秒、1接続あたり100 requests
- clientへの送信間隔: 30秒
- backendへの接続: 5秒
- backendへのrequest送信間隔: 5秒
- backendからのresponse受信間隔: 30秒

FastAPIは、JSONをparseした後のshell commandとproblem IDを検証します。
nginxの16 KiB制限は、その前段でrequest bodyを拒否します。

frontend nginxは、受信した`X-Forwarded-For`をbackendへ引き継ぎません。
`Forwarded`、`X-Forwarded-*`、`X-Real-IP`をbackendへ転送せず、
backend向けのHostもclient指定値ではなく内部upstream名へ置き換えます。
backendのUvicornはproxy headerを解釈せず、FastAPIはHostを
`backend`、`localhost`、`127.0.0.1`に限定します。
API pathの末尾slashが一致しないrequestはredirectせず404で拒否します。

問題一覧はbackend起動時にYAMLを1回だけ読み込み、
検証・JSON化した不変のsnapshotから応答します。
問題データがない場合、YAMLが不正な場合、または一覧に必要な
ID・タイトルが不正な場合はbackendを起動しません。
`/api/problems`にはETagと`Cache-Control: public, max-age=300`を付与します。

実際のclient単位のrequest頻度、burst、同時接続数は、
接続元を確認できるホスト側reverse proxy、load balancer、
またはWAFで制限します。
外側の受付制御は、インターネット公開時の必須構成です。

アプリケーションの実行slotだけでは、次の対象を十分に保護できません。

- frontend
- backend
- DB
- Docker daemon
- ホストOS

インターネット公開時は、外側の層で受付制御を行ってください。

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
- rootless環境で利用可能なseccomp・LSMによる追加制約
- 外側proxyで実際のclient単位に共有するrate・connection制限
- 複数frontend replica・複数hostで共有する受付制御
- runnerとは独立したsandbox期限強制の必要性評価
- 判定値の正規化と画像比較処理の修正
- イメージのdigest固定、SBOM、署名検証、脆弱性scan
- runnerを別hostまたは使い捨てVMへ配置する追加隔離
