# 問題データ

このディレクトリは、ShellgeiOnlineJudgeで使用する問題データの正本です。

## ディレクトリ

- `yaml_data/`: 1問に1つのYAMLファイル
- `image/`: 1問に1つの正解JPEG画像
- `v3/`: schema v3へ移行した問題定義。R3-006では代表3問だけを保持
- `semantic_manifest.json`: v3移行前の全問題definitionと正解画像のsemantic baseline

YAMLとJPEGは、`STANDARD-00000001.yaml`と
`STANDARD-00000001.jpg`のように同じファイル名にします。
ファイル名のstemがAPIのproblem IDとして使用されます。

problem IDには、次の条件があります。

- 1文字以上64文字以下
- ASCIIの英字、数字、区切りのハイフンだけを使用する
- 先頭、末尾、連続するハイフンは使用しない

R3-006時点のproduction API、runner、judgeは引き続き`yaml_data/`を参照します。
`v3/`をproductionの正本へ切り替えるのは、全問題を移行・検証する後続unitです。

## Legacy YAMLフィールド

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
| `reference_solution` | 既存`answer`から移行する参照解答。公開方法は後続unitで決定 |
| `execution.stdin` | commandへ渡す標準入力。legacy移行では空文字列 |
| `execution.fixtures` | sandboxへ配置する相対pathとUTF-8 text。legacy `input`は`input.txt`へ移行 |
| `execution.exit_code` | `ignore`または終了code 0を要求する`zero` |
| `execution.stderr` | `merge`、`ignore`、`must_be_empty` |
| `judge` | discriminator `type`が`text`なら期待出力、`image`ならartifact仕様 |

`image` judgeのartifactは、正規化された相対POSIX path、
対応する`image/jpeg`または`image/gif`、取得byte上限を明示します。
`IMAGE`問題は`image` judge、それ以外は`text` judgeだけを使用できます。

主な入力上限は次のとおりです。すべてUTF-8のbyte数で検証します。

- schema YAML: 2,000,000 byte
- title、statement、期待出力: 各field 256,000 byte
- 参照解答: 64,000 byte
- stdin: 1,000,000 byte
- fixture: 最大16件、1件および合計1,000,000 byte
- fixture/artifact path: 255 byte
- 画像artifact: 750,000 byte

fixtureとartifactのpathはabsolute path、`..`、`.`、空segment、backslash、
NULを許可しません。同一fixture pathの重複も拒否します。

現在のpilotは、入力なしtext、`input.txt` fixture付きtext、画像problemを代表する
次の3問です。

- `STANDARD-00000001`
- `PRACTICE-awk-02`
- `IMAGE-00000001`

legacy YAMLを1問移行する場合はbackend directoryから実行します。

```sh
cd backend
poetry run python -m scripts.problem_migration \
  ../problems/yaml_data/STANDARD-00000001.yaml \
  ../problems/v3/STANDARD-00000001.yaml
```

出力先はproblem IDと同名の`.yaml`に限定し、既存fileは上書きしません。
意図して置き換える場合だけ`--force`を指定します。
自動移行は、legacyの`input`を`input.txt` fixtureへ変換し、現在の挙動を表す
`exit_code: ignore`と`stderr: merge`を明示します。意味を失う可能性がある入力は
推測で変換せずエラーにします。

## 検査

legacyの必須field、YAMLとJPEGの対応、problem IDに加え、schema v3の型、
制約、pilot移行結果はDockerを使用しないbackendテストで検査します。

実際の正解コマンドをsandboxで実行する方法は、
[Docker統合テスト](../backend/tests/integration/README.md)を参照してください。

`semantic_manifest.json`は、YAMLをkey順でcanonical JSON化したSHA-256、
正解画像のSHA-256、入力有無、期待出力種別を92問すべてについて保持します。
問題データやschemaを移行する場合は、意図した変更を除いてこのbaselineと
同じ意味が保たれることをbackend testで確認してください。
