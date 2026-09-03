# SHELLGEI ONLINE JUDGE: frontend

`frontend` directoryには、ReactとTypeScriptによるブラウザ向けUIがあります。
本番用buildは、同じserviceに含まれるnginxから配信します。

## 主な構成

- `src/api/`: public APIの型、受信JSON検証、HTTP client
- `src/`: React application
- `public/`: 静的ファイル
- `nginx/`: 静的ファイルの配信とAPI proxyの設定
- `Dockerfile`: Node.js 22でbuildし、nginxで配信するmulti-stage build

提出には`POST /api/v3/submissions`を使用します。API clientはresponseを`unknown`として
受け取り、verdict、execution、artifact MIME等を実行時に検証してから画面表示用の値へ
変換します。public API contractの正本は[API仕様](../docs/API.md)です。

## 開発とテスト

Node.js、Yarn、静的検査、テスト、buildの手順は、
[開発環境の構築・テスト・起動](../docs/DEVELOPMENT.md)を参照してください。

## 参考

下記記事を参考にさせていただきました。

- nodejs and npm: https://qiita.com/nouernet/items/d6ad4d5f4f08857644de
- yarn and react: https://qiita.com/NaoyaOgura/items/cb94fefb6a63b7965f15
- nginx + react: https://www.yoheim.net/blog.php?q=20180407
