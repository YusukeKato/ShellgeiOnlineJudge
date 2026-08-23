# SHELLGEI ONLINE JUDGE

SHELLGEI ONLINE JUDGE is a shell one-liner playground: https://shellgei-online-judge.com/

シェル芸オンラインジャッジはシェル芸で問題を解いて遊ぶウェブアプリです。
ブラウザから入力されたコマンドを専用runnerがrootless Dockerのsandboxで実行し、
出力、画像、判定結果をfrontendへ返します。

## 謝辞

- [シェル芸botのDockerイメージ](https://github.com/theoremoon/ShellgeiBot-Image)を利用しています
- [jiro4989/websh](https://github.com/jiro4989/websh)のシステム構成を参考にしています

## ドキュメント

| 文書 | 対象 | 内容 |
| --- | --- | --- |
| [開発環境](./docs/DEVELOPMENT.md) | 開発者 | ローカル環境、静的検査、テスト、Compose起動 |
| [本番運用](./docs/PRODUCTION.md) | 運用者 | 本番構成、デプロイ、更新、ロールバック、監視 |
| [セキュリティ](./SECURITY.md) | 開発者・運用者 | 現在のセキュリティモデル、sandbox制限、既知の制約 |
| [セキュリティ課題](./docs/security/README.md) | 開発者・運用者 | 現在の課題、対応状況、優先順位、作業再開手順 |
| [Docker統合テスト](./backend/tests/integration/README.md) | 開発者 | Dockerテストの実行条件、コマンド、検証範囲 |
| [問題データ](./problems/README.md) | 問題作成者 | YAMLと正解画像の仕様 |
| [backend](./backend/README.md) / [frontend](./frontend/README.md) | 開発者 | 各componentの責務と主な配置 |
| [deploy](./deploy/README.md) | 開発者・運用者 | デプロイ補助スクリプト |
| [更新履歴](./UPDATE_HISTORY.md) | 利用者・開発者 | 過去のリリースとメンテナンスの履歴 |
| [AGENTS.md](./AGENTS.md) | 開発支援agent | このリポジトリで作業する際の規約 |

## 参考

- [上田ブログ/シェル芸のトップページ](https://b.ueda.tech/?page=01434)
- [theoremoon/ShellgeiBot-Image](https://github.com/theoremoon/ShellgeiBot-Image)
- [ryuichiueda/ShellGeiData](https://github.com/ryuichiueda/ShellGeiData)
- [jiro4989/websh](https://github.com/jiro4989/websh)
- [シェル芸bot](https://x.com/minyoruminyon)

## License

- [Apache License 2.0](./LICENSE)
