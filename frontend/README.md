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

提出画面は`idle`、`running`、`succeeded`、`failed`、`validation_error`を区別する
単一stateを使用します。同じ問題・commandの実行中の再送は無視し、内容が異なる新しい
提出では以前の通信を中断します。提出timeout、component破棄、問題選択変更では
`AbortController`で通信を停止し、responseの到着順にかかわらず最新requestだけを
画面へ反映します。

## 開発とテスト

Node.js、Yarn、静的検査、テスト、buildの手順は、
[開発環境の構築・テスト・起動](../docs/DEVELOPMENT.md)を参照してください。

Node.js 22系（22.22.2以上）とYarn 1.22.22を前提とします。開発serverと
production buildにはVite、component testにはVitestとjsdom、型検査にはTypeScript、
lintにはESLint flat configを使用します。build時の`VITE_*`は
ブラウザへ公開される値です。設定条件とsecurity上の制約は
[SECURITY.md](../SECURITY.md#frontendのbrowser境界)を参照してください。
