# SHELLGEI ONLINE JUDGE

SHELLGEI ONLINE JUDGE is a shell one-liner playground: https://shellgei-online-judge.com/

シェル芸オンラインジャッジはシェル芸で問題を解いて遊ぶウェブアプリです。
ブラウザから入力されたコマンドを専用runnerがrootless Dockerのsandboxで実行し、
出力、画像、判定結果をfrontendへ返します。

## 初めて開発する方へ

1. [開発手順の目的別入口](./docs/DEVELOPMENT.md#目的別の入口)で、検査だけ行うか、全体を起動するかを選びます。
2. 変更対象の[backend](./backend/README.md)・[frontend](./frontend/README.md)を読み、責務と変更箇所を確認します。
3. API変更は[API仕様](./docs/API.md)、問題変更は[作問ガイド](./docs/problem-authoring.md)、実行・隔離の変更は[SECURITY.md](./SECURITY.md)を確認します。
4. [変更の反映と検査](./docs/DEVELOPMENT.md#変更を反映する)に従って、レビュー可能なdiffと検証結果を用意します。作業・commitの規約は[AGENTS.md](./AGENTS.md)を参照してください。

Compose・sandboxの実行にはrootless Dockerが必須です。提出コマンドをホストやbackendのshellで実行しないでください。
Docker socket、資源制限、timeoutと回収、ログの保持と既知の限界は[セキュリティモデル](./SECURITY.md)を正本とします。
Dockerを使わない検査は、Docker・DB・TLSの準備なしで実行できます。

## 全体の構成

ブラウザはfrontendのnginxを経由して公開backend APIへ接続します。
backendは問題を取得し、内部runnerに実行を依頼して、結果を判定・DB保存します。
Docker socketを持つのはrunnerだけで、提出ごとの処理はsandbox内で実行します。
コードの入口と依存方向は[backendの構成](./backend/README.md#主な構成)、UIの入口は[frontendの構成](./frontend/README.md#主な構成)を参照してください。

## 開発・仕様の文書

| 文書 | 対象 | 内容 |
| --- | --- | --- |
| [開発環境](./docs/DEVELOPMENT.md) | 開発者 | 目的別の準備、検査、Compose起動、変更の反映 |
| [backend](./backend/README.md) / [frontend](./frontend/README.md) | 開発者 | 各componentの責務、提出経路、変更箇所と検査への入口 |
| [Public API](./docs/API.md) | API利用者・開発者 | request・response、HTTP statusとcache、上限、legacy互換性 |
| [Docker統合テスト](./backend/tests/integration/README.md) | 開発者 | 安全な実行条件、検査範囲の選択、必要imageと有効化flag |
| [問題作成ガイド](./docs/problem-authoring.md) / [設計記録](./docs/problem-design-notes.md) | 問題作成者 | 作問方針、設計・検証手順、各問題の学習意図 |
| [問題データ](./problems/README.md) | 問題作成者 | 現行YAML、画像、判定、manifestと移行baseline |
| [セキュリティ](./SECURITY.md) | 開発者・運用者 | 現在のセキュリティモデル、sandbox制限、既知の制約 |
| [セキュリティ課題](./docs/security/README.md) | 開発者・運用者 | 現在の課題、確認範囲、次の作業と過去の検証記録 |
| [sandbox image](./deploy/sandbox/README.md) | 開発者・運用者 | 収録コマンド、問題data、画像policy、互換性 |
| [AGENTS.md](./AGENTS.md) | 開発者・開発支援agent | 変更、検証、文書同期、Git操作の作業規約 |

## 運用・公開の文書

| 文書 | 対象 | 内容 |
| --- | --- | --- |
| [CI・供給網の検査](./docs/CI.md) | 開発者・運用者 | CI権限、scan、SBOM、provenance、依存更新 |
| [リリース手順](./docs/RELEASE.md) | 開発者・運用者 | バージョン管理、移行・復帰への入口、公開前確認 |
| [本番デプロイ](./docs/PRODUCTION.md) | 運用者 | 必要な設定、build、DB更新、起動、動作確認、障害対応 |
| [main pushからの自動更新](./docs/AUTODEPLOY.md) | 運用者 | CI成功後のSSH配備、初回設定、データ保持方針、障害対応 |
| [本番ホスト設定](./docs/PRODUCTION_HOST.md) | サーバ管理者 | 初回のrootless Docker、公開経路、TLS、再起動確認 |
| [deploy](./deploy/README.md) | 開発者・運用者 | デプロイ補助スクリプト |

## 履歴・過去の設計

| 文書 | 内容 |
| --- | --- |
| [更新履歴](./UPDATE_HISTORY.md) | 過去のリリースとメンテナンスの履歴 |
| [v3.0.0リファクタリング記録](./docs/refactoring/README.md) | 完了した31項目の設計判断・検証・commit。現行仕様の正本ではありません |
| [v3移行前のbehavior baseline](./docs/refactoring/legacy-behavior.md) | 移行前の回帰基準と、v3で修正した旧挙動 |

## 謝辞

- 旧sandboxで[シェル芸botのDockerイメージ](https://github.com/theoremoon/ShellgeiBot-Image)を利用していました。現在の構成は[独自sandbox文書](./deploy/sandbox/README.md)を参照してください
- [jiro4989/websh](https://github.com/jiro4989/websh)のシステム構成を参考にしています

## 参考

- [上田ブログ/シェル芸のトップページ](https://b.ueda.tech/?page=01434)
- [theoremoon/ShellgeiBot-Image](https://github.com/theoremoon/ShellgeiBot-Image)
- [ryuichiueda/ShellGeiData](https://github.com/ryuichiueda/ShellGeiData)
- [jiro4989/websh](https://github.com/jiro4989/websh)
- [シェル芸bot](https://x.com/minyoruminyon)

## License

- [Apache License 2.0](./LICENSE)
