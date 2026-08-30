# 問題データ

このディレクトリは、ShellgeiOnlineJudgeで使用する問題データの正本です。

## ディレクトリ

- `v3/`: productionで使用するschema v3 YAMLと`manifest.json`
- `image/`: 1問に1つの正解JPEG画像
- `yaml_data/`: v3の決定的な移行元として保持するlegacy YAML
- `semantic_manifest.json`: v3移行前の全問題definitionと正解画像のsemantic baseline

YAMLとJPEGは、`STANDARD-00000001.yaml`と
`STANDARD-00000001.jpg`のように同じファイル名にします。
ファイル名のstemがAPIのproblem IDとして使用されます。

problem IDには、次の条件があります。

- 1文字以上64文字以下
- ASCIIの英字、数字、区切りのハイフンだけを使用する
- 先頭、末尾、連続するハイフンは使用しない

backendとrunnerは起動時に`v3/`の全YAMLと`image/`の全JPEGを1回だけ読み、
schema、ID集合、画像形式・上限、`manifest.json`のrevisionを検証します。
1件でも欠損、破損、不一致があれば起動せず、request処理中は検証済みの不変な
problem repositoryだけを参照します。

## Legacy YAMLフィールド（移行baseline）

現在の問題データは、次の文字列フィールドを持ちます。

| フィールド | 用途 |
| --- | --- |
| `id` | データ管理用のproblem ID。ファイル名のstemと一致させる |
| `title_ja` / `title_en` | 日本語・英語の問題名 |
| `statement_ja` / `statement_en` | 日本語・英語の問題文 |
| `input` | 実行時にコマンドへ渡す入力データ |
| `expected_output` | 正解とする標準出力 |
| `answer` | UIに表示する解答例 |

画像を生成する問題では、コマンドから
`media/output.jpg`または`media/output.gif`へ出力します。

## Schema v3

schema v3の実行可能な型定義は
[`backend/models/problem.py`](../backend/models/problem.py)、読込とYAML変換は
[`backend/scripts/problem_schema.py`](../backend/scripts/problem_schema.py)にあります。
未知field、必須field不足、YAMLの重複key、version不一致は拒否します。

最上位fieldは次のとおりです。

| フィールド | 用途 |
| --- | --- |
| `schema_version` | 固定値`3` |
| `id` / `category` | problem IDと`STANDARD`、`PRACTICE`、`IMAGE`の分類 |
| `title` / `statement` | `ja`と`en`を持つ日英metadata |
| `reference_solution` | 既存`answer`から移行した参照解答。現行どおりpublic problem detail APIで公開する |
| `execution.stdin` | commandへ渡す標準入力。legacy移行では空文字列 |
| `execution.fixtures` | sandboxへ配置する相対pathとUTF-8 text。legacy `input`は`input.txt`へ移行 |
| `execution.exit_code` | `ignore`または終了code 0を要求する`zero` |
| `execution.stderr` | `merge`、`ignore`、`must_be_empty` |
| `judge` | discriminator `type`が`text`なら期待出力、`image`ならartifact仕様 |

`image` judgeのartifactは、正規化された相対POSIX path、
対応する`image/jpeg`または`image/gif`、取得byte上限を明示します。
`IMAGE`問題は`image` judge、それ以外は`text` judgeだけを使用できます。

### Text判定

text判定の仕様と期待出力、構造化された実行結果を受け取る純粋関数は、
[`backend/scripts/judge.py`](../backend/scripts/judge.py)を正本とします。
比較時はCRを除去し、末尾に連続するspaceとnewlineを無視します。途中のspace、
newline、tab、`NULL`等のliteral文字列は区別し、画像は判定に使用しません。

`execution.exit_code`が`zero`なら終了code 0を要求し、`ignore`なら使用しません。
`execution.stderr`の`merge`はstdout末尾へstderrを連結し、`ignore`は判定に使用せず、
`must_be_empty`はstderrが空でなければ実行失敗とします。timeoutまたは出力切り詰めが
記録された実行結果は、出力が一致しても実行失敗です。

現在のrunner protocolはstdout/stderrや終了codeをまだ分離しておらず、全92問は
互換policyの`exit_code: ignore`、`stderr: merge`です。その他のpolicyはpure judgeで
検査済みですが、production経路ではR3-013のstructured execution outcome導入まで
fail-closedで判定errorにします。

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

`v3/`にはSTANDARD 51問、PRACTICE 36問、IMAGE 5問を移行済みです。
全fileについてlegacyからの決定的な再生成結果と、問題文、入出力、参照解答、
judge種別、fixtureの意味が一致することをbackend testで確認します。

legacy YAMLを1問移行する場合はbackend directoryから実行します。

```sh
cd backend
migration_output_dir="$(mktemp -d)"
poetry run python -m scripts.problem_migration \
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
`revision`を保持します。revisionはID順に並べた全92問について、型検証後の
problem definitionをcanonical JSON化した値と、対応する正解JPEGのSHA-256から
決定的に算出します。YAMLの書式だけを変えて意味が同じ場合はrevisionは変わりません。

問題定義または正解画像を意図して変更した後は、backend directoryからmanifestを
再生成し、問題dataとmanifestを同じ変更としてreviewしてください。

```sh
cd backend
poetry run python -m scripts.problem_manifest \
  ../problems/v3 ../problems/image \
  --output ../problems/v3/manifest.json
```

生成処理自体も全YAML・JPEGを検証します。backendとrunnerは、それぞれ起動時に
checked-in manifestを再計算結果と照合します。両service間でrevisionを通信して
照合するreadiness protocolは、runner境界の後続refactoringで扱います。

## 検査

legacyの必須field、problem IDに加え、schema v3の型、YAMLとJPEGの対応、
manifest revision、全92問の移行結果はDockerを使用しないbackendテストで検査します。

実際の正解コマンドをsandboxで実行する方法は、
[Docker統合テスト](../backend/tests/integration/README.md)を参照してください。

`semantic_manifest.json`は、YAMLをkey順でcanonical JSON化したSHA-256、
正解画像のSHA-256、入力有無、期待出力種別を92問すべてについて保持します。
問題データやschemaを移行する場合は、意図した変更を除いてこのbaselineと
同じ意味が保たれることをbackend testで確認してください。
