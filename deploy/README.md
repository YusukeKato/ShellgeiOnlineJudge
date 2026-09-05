# デプロイ補助スクリプト

このディレクトリにある補助スクリプトの用途を説明します。
環境構築、テスト、本番運用の手順は、次の文書を正本とします。

- [開発環境の構築・テスト・起動](../docs/DEVELOPMENT.md)
- [本番環境の構築・デプロイ・運用](../docs/PRODUCTION.md)
- [Docker統合テスト](../backend/tests/integration/README.md)
- [セキュリティモデルと制約](../SECURITY.md)

## image構成

`sandbox/Dockerfile`は現在の問題向けの独自Ubuntu imageをbuildします。
収録内容と互換性は[sandbox文書](./sandbox/README.md)を参照してください。

`postgres/Dockerfile`は本番DBの派生imageをbuildします。
構成・更新方針は[PostgreSQL派生image](../docs/PRODUCTION.md#postgresql派生image)を正本とします。

## 補助スクリプト

`rootless-compose.sh`は次の処理を行います。

- 接続先Docker daemonがrootlessであることを確認する
- 検証後に`docker compose`を実行する
- rootless socketのパスを内部runnerのmount設定へ渡す

実行コマンドは、開発環境または本番運用の文書を参照してください。

Compose全体のE2Eと全問題の回帰テストは、pytestで明示的に有効化します。
実行条件とコマンドは[Docker統合テスト](../backend/tests/integration/README.md)を参照してください。
