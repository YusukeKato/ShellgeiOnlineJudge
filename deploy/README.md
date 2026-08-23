# デプロイ関連文書

開発環境と本番環境のどちらでもrootless Dockerを使用します。
通常ユーザーを`docker`グループへ追加する必要はありません。

- [開発環境の構築・テスト・起動](../docs/DEVELOPMENT.md)
- [本番環境の構築・デプロイ・運用](../docs/PRODUCTION.md)
- [Docker統合テスト](../backend/tests/integration/README.md)
- [セキュリティモデルと制約](../SECURITY.md)

## 補助スクリプト

`rootless-compose.sh`は次の処理を行います。

- 接続先Docker daemonがrootlessであることを確認する
- 検証後に`docker compose`を実行する
- rootless socketのパスをbackendのmount設定へ渡す

```sh
./deploy/rootless-compose.sh config --quiet
./deploy/rootless-compose.sh up -d --build
./deploy/rootless-compose.sh ps
```

`test.py`は、起動済みサービスに対して問題データの正解・不正解を実行する
end-to-end確認スクリプトです。

利用時の注意点は次のとおりです。

- 全問題のシェルコマンドを実行する
- 本番サービスや共有環境では実行しない
- 自動テストには、pytestの明示的に有効化する回帰テストを使用する

```sh
SOJ_RUN_DOCKER_TESTS=1 SOJ_RUN_FULL_REGRESSION=1 \
  poetry run pytest -m full_regression
```
