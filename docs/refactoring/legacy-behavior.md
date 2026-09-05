# v3移行前のbehavior baseline

## 目的

この文書は、R3-005で固定した移行前の回帰基準と、v3で修正した旧挙動の対応記録です。
現在のAPI仕様は[Public API](../API.md)、判定規則は[問題データ](../../problems/README.md)、
画面の状態・表示は[frontend README](../../frontend/README.md)を正本とします。

## 保持している回帰基準

- [`problems/semantic_manifest.json`](../../problems/semantic_manifest.json)は、移行前の
  legacy YAMLと正解画像のSHA-256、入力有無、期待出力種別を保持する。現在の問題構成と
  v3 manifestの役割は[問題データ](../../problems/README.md)を参照する
- legacyからv3への再生成では、問題文・fixture・参照解答等の意味を保持する
- textの空白正規化と移行済み問題のexit/stderr policyは、
  [Text判定](../../problems/README.md#text判定)に従う
- 外部client向けの旧提出形式は[legacy submission API](../API.md#legacy-submission-api)に
  限定して維持する。標準frontendはv3 APIを使用する
- 問題の空input/outputを画面で`NULL`と表示する挙動は残すが、判定時の空文字を
  literal `NULL`と同一視しない

## 移行・修正済みの挙動

以下は現在の互換性要件や未対応の不具合ではありません。
旧不具合を通常の期待値や修正待ちのxfailとして固定せず、修正後の挙動を回帰testで確認します。

| 旧挙動 | 対応unit | 現在の参照先 |
| --- | --- | --- |
| text置換token・空文字と`NULL`の衝突 | R3-010 | [Text判定](../../problems/README.md#text判定) |
| text問題への画像比較、Base64先頭除外比較 | R3-011 | [問題schemaと画像判定](../../problems/README.md#schema-v3) |
| 公開提出形式が結合出力・数字判定codeだけ | R3-016 | [v3 submission API](../API.md#v3-submission-api) |
| frontendの6要素tuple・数字codeの部分一致判定 | R3-019 | [frontend API境界](../../frontend/README.md#主な構成) |
| timeout後もfetch継続、二重送信、応答の到着順による表示競合 | R3-020 | [frontendの状態管理](../../frontend/README.md#主な構成) |
| 実行失敗・判定エラーを不正解と表示 | R3-028 | [frontendの判定表示](../../frontend/README.md#主な構成) |

`frontend/src/legacy_behavior.test.jsx`は現在もこの回帰testを保持するファイル名ですが、
内容はtyped APIと現在の表示を検証します。各unitの完了commitと検証記録は
[リファクタリングtracker](./README.md#roadmap-overview)を参照してください。
