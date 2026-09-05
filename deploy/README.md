# デプロイ補助スクリプト

このディレクトリにある補助スクリプトの用途を説明します。
環境構築、テスト、本番運用の手順は、次の文書を正本とします。

- [開発環境の構築・テスト・起動](../docs/DEVELOPMENT.md)
- [本番環境の構築・デプロイ・運用](../docs/PRODUCTION.md)
- [Docker統合テスト](../backend/tests/integration/README.md)
- [セキュリティモデルと制約](../SECURITY.md)

## 補助スクリプト

`rootless-compose.sh`は次の処理を行います。

- 接続先Docker daemonがrootlessであることを確認する
- 検証後に`docker compose`を実行する
- rootless socketのパスを内部runnerのmount設定へ渡す

実行コマンドは、開発環境または本番運用の文書を参照してください。

`test.py`は、起動済みサービスのlegacy `POST /api/shellgei`を呼ぶ手動確認スクリプトです。
problem IDはlegacy `yaml_data/`から列挙し、問題詳細APIの`answer`を実行します。
v3 submission DTO・browser操作・Compose自動起動/終了を検証するE2Eではありません。

利用時の注意点は次のとおりです。

- 全問題を対象にシェルコマンドの実行を試みる
- 本番サービスや共有環境では実行しない
- 自動テストには、pytestの明示的に有効化する回帰テストを使用する
- 問題取得失敗や参照解答欠損をskipする経路があるため、末尾の成功表示だけでは全問題の通過を保証しない

起動済みのローカル環境を対象に手動で実行する場合は、
リポジトリのルートで次を実行します。

```sh
REQUESTS_CA_BUNDLE=deploy/tls/fullchain.pem \
  SERVER_URL=https://localhost:8443 \
  poetry run python deploy/test.py
```

`REQUESTS_CA_BUNDLE`には、起動中のfrontendが使用する開発用証明書を指定します。

自動回帰テストの実行条件とコマンドは、
[Docker統合テスト](../backend/tests/integration/README.md)を参照してください。
