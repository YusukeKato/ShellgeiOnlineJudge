# SHELLGEI ONLINE JUDGE: frontend

`frontend` directoryには、ReactとTypeScriptによるブラウザ向けUIがあります。
本番用buildは、同じserviceに含まれるnginxから配信します。

## 主な構成

- `src/api/`: public APIの型、受信JSON検証、HTTP client
- `src/`: React application
- `public/`: 静的ファイル
- `index.html`、`vite.config.ts`: Viteのentry pointとbuild/test設定
- `nginx/`: 静的ファイルの配信とAPI proxyの設定
- `Dockerfile`: Node.js 22で型検査・Vite buildを行い、nginxで配信するmulti-stage build

提出には`POST /api/v3/submissions`を使用します。API clientはresponseを`unknown`として
受け取り、verdict、execution、artifact MIME等を実行時に検証してから画面表示用の値へ
変換します。public API contractの正本は[API仕様](../docs/API.md)です。

判定欄は`verdict`に従って正解・不正解・実行失敗・判定エラーを区別します。
実行失敗では、安全な`reason` enumに応じてtimeout、出力上限、非0終了code、
stderr規則違反を固定文言で説明し、それ以外やreason未指定時は一般的な実行失敗を表示します。
判定エラーにも固定文言を使用し、reasonの生値や内部例外を表示へ組み込みません。
`execution.status`や終了codeからfrontend独自の再判定は行いません。
具体的な表示mappingは[`judge_result.tsx`](./src/functions/judge_result.tsx)を参照してください。

提出画面は`idle`、`running`、`succeeded`、`failed`、`validation_error`を区別する
単一stateを使用します。`succeeded`は検証済み提出responseの受信成功であり、実行成功や
正解を意味しません。同じ問題・commandの実行中の再送は無視し、内容が異なる新しい
提出では以前の提出通信を中断します。提出timeoutやcomponent破棄でも
`AbortController`で提出通信を停止し、最新の提出responseだけを画面へ反映します。
問題詳細の取得は独立して管理し、選択変更時に以前の詳細取得を中断して最新の選択だけを
反映します。選択変更だけでは進行中の提出を中断せず、結果には提出時のproblem IDを保持します。

## 開発とテスト

Node.js、Yarn、静的検査、テスト、buildの手順は、
[開発環境の構築・テスト・起動](../docs/DEVELOPMENT.md)を参照してください。

開発serverとproduction buildにはVite、component testにはVitestとjsdom、型検査にはTypeScript、
lintにはESLint flat configを使用します。build時の`VITE_*`は
ブラウザへ公開される値です。設定条件とsecurity上の制約は
[SECURITY.md](../SECURITY.md#frontendのbrowser境界)を参照してください。
