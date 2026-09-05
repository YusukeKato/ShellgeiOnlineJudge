# v3.0.0 リリース準備

製品バージョンは`3.0.0`です。この文書は公開前の準備・確認手順です。
タグ・GitHub Releaseの公開と本番反映は、検証結果をレビューしてから行います。

## バージョンの正本

[backend/soj_shared/version.json](../backend/soj_shared/version.json)を正本とします。
backendとrunnerは同梱ファイルを読み、frontendはViteがビルド時に同じ値を埋め込みます。
画面のversionを指定する`VITE_VERSION`は廃止しました。旧`.env`に残っていても使用しません。
`VITE_UPDATE_DATE`は運用者が設定する更新日です。

Poetry・frontendのpackage versionと、本番5 imageの`org.opencontainers.image.version`ラベルは
正本の値を転記します。[整合性テスト](../backend/tests/test_release_version.py)で不一致を拒否し、
Docker統合テストで実imageのラベル、ブラウザE2Eで実画面の表示を確認します。
CIのbuild recordにも`product_version`を記録します。versionだけでは生成物を識別できないため、
配布・復帰対象はcommit・image ID・生成物hashで管理します。

バージョン更新時は正本と上記metadataを同じ差分で更新し、次を含む基本検査を実行します。

```sh
poetry run pytest backend/tests/test_release_version.py
```

public APIの`api_version`、問題の`schema_version`、runnerの`protocol_version`は
互換性を表す別の値です。製品version更新に合わせた自動変更は行いません。

## v3の変更内容

- public backendと認証付きprivate runnerを分離し、Docker操作をrunnerへ集約。
- 実行状態と判定を分離し、正解・不正解・実行失敗・判定エラーをAPIと画面で区別。
- 問題schema v3と問題revision検証、画像の画素比較、非0終了・stderrの判定規則を導入。
- 提出の二重送信・キャンセル・古い応答の表示を制御。
- DB migrationを専用処理へ分離し、通常接続の最小権限と実行ログの保持制限を導入。
- rootless Dockerの隔離・資源制限、独自Ubuntu sandbox、供給網検査とCompose/browser E2Eを整備。

APIの移行契約は[API仕様](./API.md)、問題データの移行は[問題データ文書](../problems/README.md)、
sandboxの収録コマンドは[sandbox README](../deploy/sandbox/README.md)を参照してください。

## 更新と復帰

| 対象 | 更新前に確認すること | 手順の正本 |
| --- | --- | --- |
| API利用者 | 新規clientは`/api/v3/submissions`へ対応。旧`/api/shellgei`は互換用に維持 | [API移行](./API.md) |
| 問題データ | v3変換・validation・全92問回帰を実施し、backendとrunnerのrevisionを一致させる | [問題データ](../problems/README.md) |
| サーバ設定 | rootless socket、runner認証、DB通常用／migration用URL、sandboxのimmutable IDを設定 | [本番運用](./PRODUCTION.md) |
| DB | 整合性のあるbackupと旧設定を保存。旧frontend/backendを停止して管理処理を実施 | [更新デプロイ](./PRODUCTION.md#8-更新デプロイ) |
| 障害時 | 旧image・commit・設定を保持。schema・権限・port公開の互換性を確認して復帰 | [ロールバック](./PRODUCTION.md#9-ロールバック) |

DB migration失敗時はサービス更新へ進みません。単に旧コードへ戻すだけではDB schemaと権限は戻りません。
復帰手順に従い、必要に応じて保護されたbackupを使用します。

## 公開前の確認

- 対象commitのPython・frontend基本検査、全92問、Compose/browser E2E、実imageのversion検査が成功。
- 最新の脆弱性DBによる検査、Python例外の期限・適用条件、残存リスクをレビュー。
- GitHub上のCI、required checks・review保護、署名と配布artifactの照合を確認。
- 本番の受付制御、sandbox監視、容量監視、backup・復元手順を確認。
- 検証済み生成物を本番へ反映し、提出・保存・画像表示・停止復帰を確認。
- 正本と一致する`v3.0.0`タグとリリースノートを、承認したcommitに対して公開。

CI・配布物の検証手順は[CI文書](./CI.md#生成物と検証promotion)、
未解決課題と確認状況は[セキュリティtracker](./security/README.md)を正本とします。
ローカルテストの成功だけで本番・GitHub上の確認を完了扱いにしません。
