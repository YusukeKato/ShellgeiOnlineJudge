# リリース手順

この文書は製品バージョンの管理、本番反映、GitHub Releases公開までの手順の正本です。
現在のバージョンは下記の正本、各リリースの内容は[更新履歴](../UPDATE_HISTORY.md)を参照してください。
タグ・GitHub Releaseの公開と本番反映は、検証結果をレビューしてから行います。
バージョン更新は、本番の動作確認と[GitHub Releasesへの公開・完了確認](#github-releasesへの公開と完了確認)までを含みます。

## バージョンの正本

[backend/soj_shared/version.json](../backend/soj_shared/version.json)を正本とします。
backendとrunnerは同梱ファイルを読み、frontendはViteがビルド時に同じ値を埋め込みます。
画面のversionを指定する`VITE_VERSION`は廃止しました。旧`.env`に残っていても使用しません。
`VITE_UPDATE_DATE`は画面に表示する更新日です。手動buildでは運用者が設定し、
[自動デプロイ](./AUTODEPLOY.md)ではCIで自動設定します。

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

v3系の変更概要は[更新履歴](../UPDATE_HISTORY.md#v3系の変更概要)を正本とします。
移行と復帰の判断は[次の表](#更新と復帰)を参照してください。

## 更新と復帰

| 対象 | 更新前に確認すること | 手順の正本 |
| --- | --- | --- |
| API利用者 | 新規clientは`/api/v3/submissions`へ対応。旧`/api/shellgei`は互換用に維持 | [API移行](./API.md) |
| 問題データ | 移行baselineの保持・validation・全登録問題の回帰を実施し、backendとrunnerのrevisionを一致させる | [問題データ](../problems/README.md) |
| サーバ設定 | rootless socket、runner認証、DB通常用／migration用URL、sandboxのimmutable IDを設定 | [本番運用](./PRODUCTION.md) |
| DB | 整合性のあるbackupと旧設定を保存。旧frontend/backendを停止して管理処理を実施 | [更新デプロイ](./PRODUCTION.md#更新デプロイ) |
| 障害時 | 旧image・commit・設定を保持。schema・権限・port公開の互換性を確認して復帰 | [ロールバック](./PRODUCTION.md#ロールバック) |

DB migration失敗時はサービス更新へ進みません。単に旧コードへ戻すだけではDB schemaと権限は戻りません。
復帰手順に従い、必要に応じて保護されたbackupを使用します。

## 公開前の確認

- 対象commitのPython・frontend基本検査、全登録問題の回帰、Compose/browser E2E、実imageのversion検査が成功。
- 最新の脆弱性DBによる検査、Python例外の期限・適用条件、残存リスクをレビュー。
- GitHub上のCI、required checks・review保護、署名と配布artifactの照合を確認。
- 本番の受付制御、sandbox監視、容量監視、backup・復元手順を確認。
- 検証済み生成物を本番へ反映し、提出・保存・画像表示・停止復帰を確認。

CI・配布物の検証手順は[CI文書](./CI.md#生成物と検証promotion)、
未解決課題と確認状況は[セキュリティtracker](./security/README.md)を正本とします。
ローカルテストの成功だけで本番・GitHub上の確認を完了扱いにしません。

## GitHub Releasesへの公開と完了確認

製品バージョンを上げる際は、次の公開と照合までを完了条件とします。

1. 上記の検査・署名・本番反映・動作確認に成功した対象commitの完全なSHAを記録します。
   タグとReleaseの対象には、そのSHAを明示します。
2. 正本のversionに`v`を付けたタグ名で、既存のタグとRelease（Draftを含む）を確認します。
   既存タグは実際の参照先commitを照合し、不一致なら公開を止めて原因を確認します。
   公開済みのタグとReleaseが対象に一致する場合は、その内容を確認して重複作成を避けます。
3. [更新履歴](../UPDATE_HISTORY.md)を基に、変更概要、互換性への影響、対象SHA、検証結果、
   CI・署名・配備の根拠リンクを含むリリースノートを作成してレビューします。
   残存リスクは[セキュリティtracker](./security/README.md)へのリンクで示します。
4. 未作成のversionタグを対象SHAへ作成し、同じタグでGitHub Releaseを公開します。
   通常リリースはDraft・Prereleaseを解除し、最新版（Latest）として公開します。
   タグ作成後にRelease公開が失敗した場合は、タグの参照先を再確認して公開処理を再開します。
   公開済みタグを自動で付け替えたり削除したりしません。
5. 公開後にGitHubから状態を読み直し、Release名・タグ・参照先commit・リリースノート、
   Draft・Prereleaseの解除、Latest表示、公開URLを照合します。
   本番表示と公開Releaseのversionが正本に一致したことを確認します。
6. 完了報告には公開ReleaseのURL、対象commit、検証・本番確認の結果を記載します。

CI・本番確認・Release公開の失敗時は、完了扱いや後続のブランチ整理へ進まず、
原因と未完了範囲、再開地点を報告します。
