# ShellgeiOnlineJudge 作業規約

このファイルは、リポジトリ全体を対象とする作業規約です。
実装やレビューを始める前に、変更対象に関連する既存文書も確認してください。

## 参照文書

- `README.md`: プロジェクト概要と文書索引
- `SECURITY.md`: セキュリティモデル、保証範囲、既知の制約
- `docs/security/README.md`: 現在のセキュリティ課題、対応状況、作業再開地点
- `docs/DEVELOPMENT.md`: 開発環境、テスト、ローカル起動
- `docs/PRODUCTION.md`: 本番構成、デプロイ、更新、運用
- `backend/tests/integration/README.md`: Docker統合テストの内容と実行条件
- `problems/README.md`: 問題データの構成とフィールド仕様
- `UPDATE_HISTORY.md`: リリースとメンテナンスの履歴

## サービスの前提

このサービスは、ブラウザから受け取った任意のシェルコマンドを
Docker sandboxコンテナ内で実行します。

- ユーザーが入力したコマンドを、ホストやbackendコンテナのshellで実行しないでください。
- 開発環境と本番環境のDocker daemonにはrootless Dockerを使用してください。
- rootless確認処理を迂回したり、rootful daemonへ暗黙に接続したりしないでください。
- Docker socketは強い権限を持つ境界として扱い、mountや公開範囲を広げないでください。
- sandboxのネットワーク分離、capability削除、PID・CPU・メモリ制限、
  `no-new-privileges`、tmpfs、タイムアウト、出力量制限を安易に弱めないでください。
- リクエスト間で、一時データ、コンテナ、出力、状態を共有しないでください。
- timeoutや例外が発生した場合も、実行処理とコンテナを確実に終了・破棄してください。
- `.env`、TLS秘密鍵、認証情報などの秘密情報をコミットしないでください。

隔離方式や制限値を変更する場合は、先に`SECURITY.md`を確認し、
影響範囲、互換性、失敗時の挙動、必要なテストを整理してください。

fork bomb、ディスク枯渇、大量コンテナ生成、Docker daemon停止などの耐性試験は、
通常の開発PCや本番ホストでは実行しないでください。
必要な場合は、watchdogと復元手段を備えた使い捨て環境を使用してください。

## 実装方針

- 変更前に、APIからsandbox実行、判定、DB保存までのデータフローを確認してください。
- 問題を再現・特定してから、必要な範囲に限定して変更してください。
- 大規模な全面書き換えより、レビュー可能な小さな変更を優先してください。
- HTTP API、問題データ、判定方法、frontendから見た動作を可能な限り維持してください。
- セキュリティ上の理由で互換性を変更する場合は、理由、影響、代替案を説明してください。
- API層、判定処理、Docker操作、DB処理の責務を混在させないでください。
- 並行実行、timeout、キャンセル、終了処理に関わるコードは、
  race conditionとリソースリークを考慮してください。
- 新しい依存関係は必要性を確認し、追加した場合はlock fileも更新してください。
- 既存の未コミット変更を保持し、依頼と無関係な差分を変更しないでください。

## ドキュメントの同期

実装、設定、コマンド、環境変数、API、セキュリティ上の保証、制約、
デプロイ方法、運用手順を変更した場合は、影響する既存文書も同じ変更内で更新してください。

特に、次の対応関係を確認してください。

- 開発手順やテスト方法: `docs/DEVELOPMENT.md`
- 本番構成、デプロイ、運用: `docs/PRODUCTION.md`
- sandbox、Docker socket、制限、既知のリスク: `SECURITY.md`
- Docker統合テストの条件や内容: `backend/tests/integration/README.md`
- 問題データの構成やfield: `problems/README.md`
- プロジェクト全体の文書索引: `README.md`
- backendまたはfrontend固有の手順: 各ディレクトリの`README.md`

文書は変更履歴として追記するのではなく、現在の仕様と手順が分かるように更新してください。
コードと文書が矛盾する状態を残さないでください。

## 検査とテスト

変更範囲に対応するテストを追加または更新し、実行可能な検査を実施してください。
実行しなかった検査やskipされたテストがある場合は、理由と未確認範囲を報告してください。

Pythonコードを変更した場合の基本検査は次のとおりです。

```sh
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy .
poetry run pytest -m "not docker"
```

frontendを変更した場合の基本検査は次のとおりです。

```sh
cd frontend
yarn format:check
yarn lint
CI=true yarn test --watchAll=false
yarn build
```

Docker実行処理やsandbox設定を変更した場合は、rootless daemonを明示し、
必要に応じてDocker統合テストを実行してください。

```sh
export DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
SOJ_RUN_DOCKER_TESTS=1 poetry run pytest -m docker
```

全問題回帰テストは明示的に有効化します。

```sh
SOJ_RUN_DOCKER_TESTS=1 SOJ_RUN_FULL_REGRESSION=1 \
  poetry run pytest -m full_regression
```

Compose構成を変更した場合は、rootless確認を含む補助スクリプトで検証してください。

```sh
./deploy/rootless-compose.sh config --quiet
```

## Git操作

- コミットは、依頼者から明示的な承認または依頼があった場合だけ実行してください。
- pushは依頼者が行うため、明示的に依頼されない限り実行しないでください。
- コミット前に対象ファイルと差分を提示し、関連する変更だけを含めてください。
