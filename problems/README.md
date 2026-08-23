# 問題データ

このディレクトリは、ShellgeiOnlineJudgeで使用する問題データの正本です。

## ディレクトリ

- `yaml_data/`: 1問に1つのYAMLファイル
- `image/`: 1問に1つの正解JPEG画像

YAMLとJPEGは、`STANDARD-00000001.yaml`と
`STANDARD-00000001.jpg`のように同じファイル名にします。
ファイル名のstemがAPIのproblem IDとして使用されます。

problem IDには、次の条件があります。

- 1文字以上64文字以下
- ASCIIの英字、数字、区切りのハイフンだけを使用する
- 先頭、末尾、連続するハイフンは使用しない

## YAMLフィールド

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

## 検査

必須フィールドの型、YAMLとJPEGの対応、problem IDの形式は、
Dockerを使用しないbackendテストで検査します。

実際の正解コマンドをsandboxで実行する方法は、
[Docker統合テスト](../backend/tests/integration/README.md)を参照してください。
