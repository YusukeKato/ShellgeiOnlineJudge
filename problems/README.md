# 問題データ

このディレクトリは、ShellgeiOnlineJudgeで使用する問題データの正本です。
作成前の設計方針は[問題作成ガイド](../docs/problem-authoring.md)、
各問題の狙いは[設計記録](../docs/problem-design-notes.md)を参照してください。

## ディレクトリ

- `v3/`: productionで使用するschema v3 YAMLと`manifest.json`
- `image/`: 全問題の表示・判定用JPEG。GIF artifact問題では同じIDの判定用GIFも配置する
- `legacy_image/`: 改訂前の正解JPEG。移行baselineの検査専用で、表示・判定には使用しない
- `yaml_data/`: v3の決定的な移行元として保持するlegacy YAML
- `semantic_manifest.json`: v3移行前の全問題definitionと正解画像のsemantic baseline

YAMLとJPEGは、`STANDARD-00000001.yaml`と
`STANDARD-00000001.jpg`のように同じファイル名にします。
ファイル名のstemがAPIのproblem IDとして使用されます。

problem IDには、次の条件があります。

- 1文字以上64文字以下
- ASCIIの英字、数字、区切りのハイフンだけを使用する
- 先頭、末尾、連続するハイフンは使用しない

backendとrunnerは起動時に`v3/`の全YAMLと`image/`の全JPEG・判定用GIFを1回だけ読み、
schema、ID集合、画像形式・上限、`manifest.json`のrevisionを検証します。
この検査で欠損や不一致を検出すると起動せず、request処理中は不変なproblem repositoryを
参照します。起動時の画像検査はbyte上限とJPEG/GIFの先頭・末尾markerの確認に限定され、
完全decodeによる破損検出は行いません。markerを満たす破損画像は起動時検査を通過し得るため、
正解画像の更新時には実際のdecodeと画像問題回帰も確認してください。

text問題にも表示用JPEGを配置する必要があります。現在は同一の白画像を使用していますが、
repositoryのID集合検査と問題詳細APIが依存しているため、単独では削除できません。

## Legacy YAMLフィールド（移行baseline）

移行元の`yaml_data/`は、次の文字列フィールドを持ちます。

| フィールド | 用途 |
| --- | --- |
| `id` | データ管理用のproblem ID。ファイル名のstemと一致させる |
| `title_ja` / `title_en` | 日本語・英語の問題名 |
| `statement_ja` / `statement_en` | 日本語・英語の問題文 |
| `input` | 実行時にコマンドへ渡す入力データ |
| `expected_output` | 正解とする標準出力 |
| `answer` | 参照解答。v3の`reference_solution`へ移行する |

画像を生成する問題では、コマンドから
`media/output.jpg`または`media/output.gif`へ出力します。

## sandboxに収録する参照data

問題の一部は`input.txt`以外に`/ShellGeiData`の公開dataを参照します。
収録範囲、取得元・build時の最新revisionの記録方法、利用条件は
[sandbox文書](../deploy/sandbox/README.md#収録するもの)を正本とします。
追加の固定textは`execution.fixtures`で配置できます。fixtureでは扱えないdataをimageへ
収録する必要がある場合は、sandbox構成も更新してください。
新規問題と公開data更新の互換性は、全問題回帰で確認してください。

## Schema v3

schema v3の実行可能な型定義は
[`backend/soj_shared/models/problem.py`](../backend/soj_shared/models/problem.py)、読込とYAML変換は
[`backend/soj_shared/problem_schema.py`](../backend/soj_shared/problem_schema.py)にあります。
未知field、必須field不足、YAMLの重複key、version不一致は拒否します。

最上位fieldは次のとおりです。

| フィールド | 用途 |
| --- | --- |
| `schema_version` | 固定値`3` |
| `id` / `category` | problem IDと`STANDARD`、`PRACTICE`、`IMAGE`の分類 |
| `title` / `statement` | `ja`と`en`を持つ日英metadata |
| `reference_solution` | 参照解答。public problem detail APIで公開する |
| `execution.stdin` | commandへ渡す標準入力。legacy移行では空文字列 |
| `execution.fixtures` | sandboxへ配置する相対pathとUTF-8 text。legacy `input`は`input.txt`へ移行 |
| `execution.exit_code` | `ignore`または終了code 0を要求する`zero` |
| `execution.stderr` | `merge`、`ignore`、`must_be_empty` |
| `judge` | discriminator `type`が`text`なら期待出力、`image`なら比較方式とartifact仕様 |

`image` judgeのartifactは、正規化された相対POSIX path、
対応する`image/jpeg`または`image/gif`、取得byte上限を明示します。
`IMAGE`問題は`image` judge、それ以外は`text` judgeだけを使用できます。

画像問題は`judge.comparison: exact_pixels`を必須とします。runnerは
`judge.artifact.path`で指定された1fileだけを取得し、同じdirectoryの別JPEG/GIFを
候補として探索しません。runnerは問題別の取得byte上限を適用し、judgeは欠損、
Base64破損、宣言MIMEとJPEG/GIF形式の不一致、decode上限超過を拒否します。
pure image judge単体では問題別のbyte上限を再検証しません。
正解画像と提出画像をRGBAへdecodeし、寸法、frame数、全画素が完全一致する場合だけ
正解です。metadata等の画素へ影響しないencoder差は判定に使用しませんが、
JPEG品質変更や再圧縮によって画素が変わる場合は不正解になります。

旧方式のようにBase64先頭28文字を無条件に除外せず、画像headerと形式を検証してから
全画素を比較します。画像生成toolやdecoderを変更するときは、5画像問題のrootless
Docker回帰を実行してください。

### Text判定

text判定の仕様と期待出力、構造化された実行結果を受け取る純粋関数は、
[`backend/soj_backend/judge.py`](../backend/soj_backend/judge.py)を正本とします。
比較時はCRを除去し、末尾に連続するspaceとnewlineを無視します。途中のspace、
newline、tab、`NULL`等のliteral文字列は区別し、画像は判定に使用しません。

`execution.exit_code`が`zero`なら終了code 0を要求し、`ignore`なら使用しません。
`execution.stderr`の`merge`はstdout末尾へstderrを連結し、`ignore`は判定に使用せず、
`must_be_empty`はstderrが空でなければ実行失敗とします。timeoutまたは出力切り詰めが
記録された実行結果は、出力が一致しても実行失敗です。

runner protocolはstdout、stderr、終了code、timeout、切り詰めを分離して保持し、
production判定にも上記policyを適用します。移行済みの全92問は、従来挙動を維持する
`exit_code: ignore`、`stderr: merge`です。

主な入力上限は次のとおりです。すべてUTF-8のbyte数で検証します。

- schema YAML: 2,000,000 byte
- title、statement、期待出力: 各field 256,000 byte
- 参照解答: 64,000 byte
- stdin: 1,000,000 byte
- fixture: 最大16件、1件および合計1,000,000 byte
- fixture/artifact path: 255 byte
- 画像artifact: 750,000 byte

fixtureとartifactのpathはabsolute path、`..`、`.`、空segment、backslash、
NULを許可しません。同一fixture pathの重複と、提出command用に予約した
`z.bash`も拒否します。

`v3/`にはSTANDARD 52問、PRACTICE 36問、IMAGE 5問の計93問があります。
移行元92問のうち未改訂の問題は、legacyからの決定的な再生成結果との一致を検査します。
意図した改訂は、[改訂登録](../backend/tests/fixtures/problem_revisions.json)の変更field一覧と
定義hashで限定し、画像改訂は現行JPEGのhashも登録します。旧JPEGは`legacy_image/`へ保存し、
移行前のsemantic baselineとの照合を維持します。未変更field・実行policy・judge種別の保持も検査します。
改訂内容の正本はv3 YAML、学習意図は[設計記録](../docs/problem-design-notes.md)です。

新規問題は`v3/`と対応画像へ追加し、manifestも再生成します。
`yaml_data/`と`semantic_manifest.json`は移行baselineとして保持し、新問を追加しません。
legacyのID集合がv3に含まれることと、現行の全YAML・JPEGのID集合およびmanifestの一致を
別々に検査します。既存問題の意図した修正では、改訂登録も同じdiffでレビューしてください。
改訂hashは型付き定義のJSON（UTF-8、key昇順、ensure_ascii=False、区切りは`,`と`:`）のSHA-256です。
変更fieldはlegacyのfield名で列挙し、移行元YAMLとsemantic manifestを改訂後の内容で上書きしません。

legacy YAMLを1問移行する場合はbackend directoryから実行します。

```sh
cd backend
migration_output_dir="$(mktemp -d)"
poetry run python -m soj_tools.problem_migration \
  ../problems/yaml_data/STANDARD-00000001.yaml \
  "${migration_output_dir}/STANDARD-00000001.yaml"
```

出力先はproblem IDと同名の`.yaml`に限定し、既存fileは上書きしません。
意図して置き換える場合だけ`--force`を指定します。
自動移行は、legacyの`input`を`input.txt` fixtureへ変換し、現在の挙動を表す
`exit_code: ignore`と`stderr: merge`を明示します。意味を失う可能性がある入力は
推測で変換せずエラーにします。

## Problem data revision

`v3/manifest.json`はmanifest/schema version、問題数、64文字のSHA-256
`revision`を保持します。revisionはID順に並べた全問題について、型検証後の
problem definitionと各recordの`answer_image`のSHA-256をcanonical JSON化して
決定的に算出します。`answer_image`は通常JPEG、GIF問題では判定用GIFです。
GIF問題の表示用JPEGは起動時検査の対象ですが、revisionの対象には含まれません。
YAMLの書式だけを変えて意味が同じ場合はrevisionは変わりません。

問題定義または正解画像を意図して変更した後は、backend directoryからmanifestを
再生成し、問題dataとmanifestを同じ変更としてreviewしてください。

```sh
cd backend
poetry run python -m soj_tools.problem_manifest \
  ../problems/v3 ../problems/image \
  --output ../problems/v3/manifest.json
```

生成処理も上記の起動時検査と同じ検証を使用します。backendとrunnerは、それぞれ起動時に
checked-in manifestを再計算結果と照合します。実行requestとresponseでもrevisionを
相互検証し、不一致を拒否します。通信契約とreadinessは
[内部runner protocol](../backend/README.md#内部runner-protocol)を参照してください。

## 検査

legacyの必須field、problem IDに加え、schema v3の型、YAMLとJPEGの対応、
manifest revision、全92問の移行結果はDockerを使用しないbackendテストで検査します。

実際の正解コマンドをsandboxで実行する方法は、
[Docker統合テスト](../backend/tests/integration/README.md)を参照してください。

`semantic_manifest.json`は、YAMLをkey順でcanonical JSON化したSHA-256、
正解画像のSHA-256、入力有無、期待出力種別を92問すべてについて保持します。
問題データやschemaを移行する場合は、意図した変更を除いてこのbaselineと
同じ意味が保たれることをbackend testで確認してください。
