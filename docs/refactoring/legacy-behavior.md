# v3移行前のbehavior baseline

## 目的

この文書は、R3-005で固定したv2系のproblem、judge、API、frontendの挙動と、
互換性として維持せず後続unitで修正する既知不具合を区別する正本です。
実際の入力と期待値はcharacterization testおよび
[`problems/semantic_manifest.json`](../../problems/semantic_manifest.json)を参照してください。

## 維持するbaseline

- problem corpusは92問で、STANDARD 51問、PRACTICE 36問、IMAGE 5問
- 入力データを持つ問題は68問、空の期待出力を持つ問題はIMAGEの5問
- 各問題のYAML definitionと正解JPEGはsemantic manifestのSHA-256で固定する
- legacy judgeはtext一致とimage一致の組み合わせをverdict `1`から`4`で返す
- text比較ではCRを除去し、末尾のspaceとnewlineを無視するが、tabは区別する
- public APIのsubmission結果は`output`、`id`、`date`、`judge`、`image`を返す
- frontendはsubmission結果を5要素tupleへ変換し、問題の空input/outputを`NULL`と表示する
- frontendのclient-side timeout表示は20秒で、結果textとimage data URLをDOMへ渡す

## 既知不具合として修正する挙動

次の挙動は互換性要件ではありません。現在の誤動作を通常の期待値として固定せず、
backendではstrict xfail、frontendでは後続unitの修正対象として追跡します。

- judgeの文字列置換後に`SPACE`、`NEWLINE`、`TAB`、`LT`、`GT`がliteral出力と衝突する
- 空出力を表す内部文字列`NULL`と、利用者が出力したliteral `NULL`が衝突する
- Base64文字列の先頭28文字を除外するため、画像先頭21 byteの差を検出できない
- frontendはverdict文字列に`1`が含まれるだけで正解表示にする
- frontend timeoutは進行中の`fetch`を中断しない
- infrastructure errorとjudge errorをtyped stateで区別せず、不正解表示へ変換し得る

これらはR3-009からR3-020の対応unitで型付き境界へ移行し、
修正時に該当xfailまたは追跡項目を通常の成功testへ置き換えます。
