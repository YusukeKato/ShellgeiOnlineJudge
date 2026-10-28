# SHELLGEI ONLINE JUDGE: frontend

`frontend` directoryには、ReactとTypeScriptによるブラウザ向けUIがあります。
本番用buildは、同じserviceに含まれるnginxから配信します。

- [開発とテスト](#開発とテスト)
- [主な構成](#主な構成) / [変更箇所の案内](#変更箇所の案内)
- [画面と通信の契約](#画面と通信の契約)
- [問題を指定する共有URL](#問題を指定する共有url)
- [依存更新時の注意](#依存更新時の注意)

## 開発とテスト

この文書で案内する開発経路は、Composeでの全体起動と、ホスト上でのfrontendの検査です。
Node.js、Yarnの準備、静的検査、テスト、buildとCompose起動・変更の反映は、
[開発環境の構築・テスト・起動](../docs/DEVELOPMENT.md)を参照してください。
実ブラウザから本番imageの提出・表示・DB保存まで確認する手順は、
[ComposeとブラウザのE2E](../backend/tests/integration/README.md#composeとブラウザのe2e)を参照してください。

`package.json`の`yarn start`はViteの開発serverを起動します。
Viteの開発serverとComposeのAPIを接続する手順は未検証です。
現在の`vite.config.ts`にはAPI proxy設定がなく、`VITE_SOJ_URL`未設定時は開発server自身のoriginへAPI requestを送ります。
Composeで起動した全体と、ホスト上の検査の手順を使用してください。

build時の`VITE_*`はブラウザへ公開される値です。設定条件とsecurity上の制約は
[SECURITY.md](../SECURITY.md#frontendのbrowser境界)を参照してください。

## 主な構成

- `src/api/`: public APIの型、受信JSON検証、HTTP client
- `src/`: React application
- `src/language.tsx`: 日英の表示切替と端末内の設定保存
- `src/css/design.css`: 共通スタイルとレスポンシブレイアウト
- `src/images/BlueTreeIcon.jpg`: ヘッダーアイコン（[提供元](https://github.com/YusukeKato/YusukeKatoBlog/blob/main/static/images/BlueTreeIcon.jpg)から取得し、サイト内で配信）
- `public/`: 静的ファイル
- `index.html`、`vite.config.ts`: Viteのentry pointとbuild/test設定
- `nginx/`: 静的ファイルの配信とAPI proxyの設定
- `Dockerfile`: Node.js 22で型検査・Vite buildを行い、nginxで配信するmulti-stage build

## 変更箇所の案内

| 変更したい内容              | 最初に読む実装                                                                         |
| --------------------------- | -------------------------------------------------------------------------------------- |
| 画面構成・スタイル          | `src/tsx/`、`src/css/design.css`                                                       |
| APIの型・受信検証・通信     | `src/api/types.ts`、`src/api/client.ts`。公開契約は[API仕様](../docs/API.md)           |
| 提出状態・結果表示          | `src/functions/submit.tsx`、`src/functions/judge_result.tsx`、`src/tsx/playground.tsx` |
| 問題選択・共有URL・詳細取得 | `src/tsx/playground.tsx`、`src/functions/update_problem.tsx`                           |
| 日英表示・外部リンク        | `src/language.tsx`、`src/links.ts`                                                     |
| 配信・API proxy・build設定  | `nginx/default.conf`、`Dockerfile`、`vite.config.ts`                                   |

## 画面と通信の契約

### 言語とレイアウト

ヘッダーの「日本語 / English」で、問題名・問題文・操作文言を切り替えます。
初期値は日本語で、選択はlocalStorageの`soj-language`へ保存し、`html lang`も同期します。
storageを使えない環境でも切替可能です。言語変更では問題を再取得せず、入力・選択・提出・結果を保持します。
コマンドと入出力データは翻訳しません。通信・入力検証・実行失敗・判定エラーの説明は英語です。

PCでは問題選択・問題文と入力・結果を2列、1,024px未満では1列に配置します。
問題一覧は問題文と同じ幅の折りたたみから選択でき、入出力の長い行はコード枠内で横スクロールします。
結果には提出時の問題ID・実行時間・提出IDを示し、artifactがない場合は画像枠を表示しません。
生成GIFは`media/output.gif`へ保存すると表示できます。判定用画像との優先順位・制限は[API仕様](../docs/API.md)を参照してください。

案内と提出情報の折りたたみ欄は、末尾の「閉じる / Close」からも閉じられます。
閉じるとその欄の見出しへフォーカスを戻し、他の欄の開閉状態や入力・提出結果を保持します。

### 外部client向けの提出・問題取得例

コマンド入力下に「ターミナルから実行する（curl）」と「Pythonスクリプトから実行する」を表示します。
どちらも現在の入力と選択中の問題を反映し、空欄ではサンプルを使います。
curlはJSONの引用符・改行を自動でescapeし、引用したheredocから送信します。
Python 3は追加依存なしの`urllib.request`で提出し、`json.load`で応答を読み、
判定と`repr`形式の標準出力・標準エラーを表示します。全文を`submit.py`へ保存して実行できます。
両方の案内に、問題一覧と選択中の問題詳細をGETするコピー可能な例も表示します。
Pythonの取得例は`problems.py`として単独実行でき、取得した一覧・詳細を表示します。
`input`（`input.txt`の内容）、`expected_output`、`answer`の読み方を案内し、
取得例からは提出や回答例の実行を行いません。fieldとendpointの正本は[API仕様](../docs/API.md#problem-api)です。
送信先は画面のAPIと同じ`VITE_SOJ_URL`（未設定なら現在のorigin）です。
コピーボタンは表示中の全文をコピーし、Clipboard APIが利用できない場合はコードを選択して手動コピーを案内します。

### 外部リンク

「使い方・情報 / About」と共通フッターからGoogleフォームを別タブで開けます。
リンク先は[`links.ts`](./src/links.ts)で管理します。

### API受信と判定表示

提出には`POST /api/v3/submissions`を使用します。API clientはresponseを`unknown`として
受け取り、verdict、execution、artifact MIME等を実行時に検証してから画面表示用の値へ
変換します。public API contractの正本は[API仕様](../docs/API.md)です。

問題一覧・詳細の取得も、API clientのtimeoutMs指定時はheader待ちからJSON解析までを期限対象にします。
指定しない場合の既存動作は維持し、呼出側signalによる中断とtimeoutを別のエラーとして扱います。
成功・失敗・中断のいずれでもtimerと中断listenerを回収します。

判定欄は`verdict`に従って正解・不正解・実行失敗・判定エラーを区別します。
正解・不正解のラベルは選択言語に従い、実行失敗・判定エラーのラベルと詳細は固定英文です。
実行失敗では、安全な`reason` enumに応じてtimeout、出力上限、非0終了code、
stderr規則違反を固定文言で説明し、それ以外やreason未指定時は一般的な実行失敗を表示します。
判定エラーにも固定文言を使用し、reasonの生値や内部例外を表示へ組み込みません。
`execution.status`や終了codeからfrontend独自の再判定は行いません。
具体的な表示mappingは[`judge_result.tsx`](./src/functions/judge_result.tsx)を参照してください。

### 提出状態と通信の中断

提出画面は`idle`、`running`、`succeeded`、`failed`、`validation_error`を区別する
単一stateを使用します。`succeeded`は検証済み提出responseの受信成功であり、実行成功や
正解を意味しません。同じ問題・commandの実行中の再送は無視し、内容が異なる新しい
提出では以前の提出通信を中断します。提出timeoutやcomponent破棄でも
`AbortController`で提出通信を停止し、最新の提出responseだけを画面へ反映します。
問題詳細の取得は独立して管理し、選択変更時に以前の詳細取得を中断して最新の選択だけを
反映します。選択変更だけでは進行中の提出を中断せず、結果には提出時のproblem IDを保持します。

## 問題を指定する共有URL

`/?problem=STANDARD-00000052`のように`problem`へ問題IDを指定すると、その問題を選択して開きます。
`PRACTICE-...`・`IMAGE-...`・`REGEX-...`も同じ形式で、問題一覧のカテゴリを選択問題へ合わせます。
パラメータなしでは通常問題1（`STANDARD-00000001`）を表示します。

画面で問題を選ぶとURLを更新し、ブラウザの戻る・進むでも選択を復元します。
問題以外のqueryとfragmentは保持します。入力・提出中の通信・結果は問題選択だけではリセットしません。
URLにコマンドは保存せず、共有URLを開いただけで提出を実行することもありません。

空・形式不正・64文字超・複数の`problem`指定、存在しない問題（詳細APIの404）は、
固定英文で案内して通常問題1へ戻し、URLを履歴追加なしで置き換えます。
通信障害や500等は取得エラーとして表示し、問題IDの誤りと扱いません。
通常問題1自体が取得できない場合も取得エラーを表示し、再帰的に切り替えません。

## 依存更新時の注意

開発serverとproduction buildにはVite、component testにはVitestとjsdom、型検査にはTypeScript、
lintにはESLint flat configを使用します。TypeScriptは`typescript-eslint`の対応範囲に合わせて
6.0系を使用し、`tsconfig.json`の`paths`は設定ファイルからの相対pathで指定します。
TypeScriptを更新する場合はlint側のpeer dependencyも確認してください。
Vitest 5では、`setupTests.js`でjest-domの公開matcherを`expect.extend`へ登録し、
`vitest.d.ts`で`Matchers<R, T>`を拡張しています。jest-dom 7.0.1の`/vitest` entryは
旧`Assertion`型を宣言して衝突するため使用しません。同期・非同期の戻り値の型と
一致・不一致時の動作は`matchers.test.ts`で確認します。
jest-domの連携方法を更新するときも、型検査を省略せずこの契約を維持してください。

runtime imageのbase digestとOS packageの固定値は[`Dockerfile`](./Dockerfile)を正本とします。
本番imageでは使わないcurl/libcurlを削除しています。利用者の端末向けcurl例は引き続き表示します。
固定packageが配布元から消えた場合は、同じAlpine branchで配布中の候補を確認し、
[image更新の検証手順](../docs/PRODUCTION.md#image-digestの更新)を通して固定値を更新してください。

製品versionの管理とv3移行の概要は[リリース手順](../docs/RELEASE.md)を参照してください。
