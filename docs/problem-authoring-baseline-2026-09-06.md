# 問題作成の過去調査（2026-09-06）

この文書は、問題作成方針を検討した当時の調査記録です。
対象はcommit `31d911ea34458dcb4e55cf35762be345d8ef28af`であり、
問題数、コマンドの集計、問題への評価は、その時点のデータについて記したものです。
YAMLへのリンクも対象commitに固定しています。現行問題の仕様や評価の裏付けには使わず、
現在の[問題作成ガイド](problem-authoring.md)と[設計記録](problem-design-notes.md)を参照してください。
この移動に伴う過去集計の再実施はしていません。

## 既存問題から分かること

以下は2026-09-06、commit `31d911e`時点の調査です。
`problems/v3/`の全92問の日本語問題文・参照解答を読み、代表例の入力・期待出力を照合しました。
設計上の評価は参照解答から読み取ったもので、元の作者の意図を断定するものではありません。
問題を追加・修正するときは、以下の集計だけに頼らず、その時点の問題群を確認してください。
STANDARD-00000003・05〜51、PRACTICE全36問、IMAGE全5問はこの調査後に改訂しました。
以下の旧問題への評価は調査時点のもので、
改訂後の学習意図は[設計記録](problem-design-notes.md)を参照してください。

### 構成と偏り

| 区分 | 問題数 | 主な傾向 |
| --- | ---: | --- |
| STANDARD | 51 | 入出力入門、数値計算、アルゴリズム、文字列変換、模様の生成。参照解答の41問にawkが登場する |
| PRACTICE | 36 | コマンド名を明示する基礎練習。awk 8、sed 6、cat・grep各4、echo・find・sort・wc各3、uniq 2問 |
| IMAGE | 5 | convertによる単色画像・線・円・四角の生成。調査時点の判定画像は全てJPEG |

調査時点のcategoryは分類であり、難易度を表すschema fieldではありません。
入力は68問が`input.txt`を1つ持ち、24問がfixtureなしです。標準入力を設定した問題はありません。
fixtureなしでも、問題文の条件や環境内のデータを使う問題があります。

| 参照解答に登場するコマンド | 問題数 |
| --- | ---: |
| awk | 49 |
| sed | 20 |
| sort | 12 |
| xargs | 8 |
| grep、tr | 各6 |
| uniq、convert | 各5 |
| find | 4 |
| cut、seq、factor | 各2 |
| rs | 1 |
| paste、comm、join、head、tail、tac、rev、fold | 各0 |

同一コマンドが1問に何回登場しても1件とし、`xargs`から呼ぶ`grep`も含めます。
これは参照解答の登場数であり、使用必須のコマンド数や別解の有無ではありません。
入力を渡すための`cat`や、awk内の`printf`などはこの表から除いています。

参照解答では、grepへの過度な偏りよりも、awkでループや条件分岐を書く例の多さが目立ちます。
これは解答例の傾向であり、各問題がawkを要求していることや、他の道具では解けないことを示しません。
列の入れ替えや文字から行への変換はありますが、2つのデータの集合演算・キー結合は手薄です。
複数fixtureを使う問題もなく、ファイル探索は主にShellGeiDataを対象にしています。

### 設計の参考になる例

| 既存問題 | 解法の核と評価 | 新しい設計で気を付けること |
| --- | --- | --- |
| [STANDARD-00000011：行列の回転](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/STANDARD-00000011.yaml) | `rs -T`で転置し、awkで列順を反転する。「回転」を既存の変換へ分解できる | 固定3列の想定解。任意サイズ対応を問題文で約束しない |
| [STANDARD-00000014：グループ分け](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/STANDARD-00000014.yaml) | 安定ソートとグループ単位の整形。キーでまとめながら元の順序を残す意味がある | グループ番号の欠番や同一キー内の順序など、前提を明確にする |
| [STANDARD-00000040：文字カウント2](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/STANDARD-00000040.yaml) | 文字を行へ変換し、`sort \| uniq -c`で集計する。道具が扱える単位へ見方を変える | 参照解答に生じる空行を取り除く処理まで含め、各段の役割を説明できるようにする |
| [STANDARD-00000048：文字列の圧縮](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/STANDARD-00000048.yaml) | `uniq -c`を連続区間の長さに使う。全体の頻度集計とは異なる | 同じ文字が離れて再登場する入力も検討する。既存入力だけでは、誤ってsortする解法との差が出ない |
| [STANDARD-00000051：打率ランキング](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/STANDARD-00000051.yaml) | awkの計算・整形とsortの数値キー・同率時の第2キーが自然につながる | 丸め前・丸め後のどちらで順位を決めるか、同率や分母0の扱いを設計時に決める |
| [STANDARD-00000009：日記の並べ替え](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/STANDARD-00000009.yaml) | 複数行の記録を一時的に1行へまとめ、並べ替えて戻す発想がある | 本文中の空白を扱えるか、日時の昇順・降順はどちらかを明記する。既存参照解答は空白で分割し、日付の降順にする |
| [STANDARD-00000012：ビットの反転](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/STANDARD-00000012.yaml) | `tr 01 10`による文字集合の対応。1コマンドでも、逐次置換とは違う学びがある | コマンド数を増やすための前処理を付け足さない |
| [STANDARD-00000044：文字列の検索](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/STANDARD-00000044.yaml) | ファイルの探索、内容の検索、名前の抽出をつなぐ | 外部データの版、出力順、ファイル名の空白などを確認する |

### 基礎練習・重複・見直しの観点

- `PRACTICE-grep-*`、`PRACTICE-sort-*`などの単独操作は、基礎練習として役割があります。
  新しく同種の問題を増やす場合は、既存の練習では学べない内容を示してください。
- [PRACTICE-sort-03](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/PRACTICE-sort-03.yaml)と
  [PRACTICE-uniq-01](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/PRACTICE-uniq-01.yaml)は、異なる道具で整列・重複除去を扱います。
  比較学習には使えますが、数値と単語を変えただけの追加は学びが重なります。
  `PRACTICE-awk-04`と`PRACTICE-wc-01`の行数、`PRACTICE-awk-05`と
  `STANDARD-00000003`の列生成にも同様の重なりがあります。
- [STANDARD-00000010：虫食い日記](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/STANDARD-00000010.yaml)は、指定された語を
  指定箇所へ埋める作業が中心です。応用問題を追加する際の手本にはせず、置換の基礎練習と区別します。
- [STANDARD-00000017](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/STANDARD-00000017.yaml)はsortを、
  [STANDARD-00000020](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/STANDARD-00000020.yaml)はfactorを使わない課題です。
  アルゴリズム学習としての意味はありますが、Unixの道具を発見する目的とは別です。
  新問では便利な道具を禁止して難しさを作ることを標準にしません。
- [STANDARD-00000024：ナップサック問題](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/STANDARD-00000024.yaml)や
  [STANDARD-00000026：最短経路探索](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/STANDARD-00000026.yaml)の参照解答は
  awk内の多重ループや状態管理が中心です。単に一般のプログラムをawkへ移した問題を増やさず、
  awkの連想配列やストリーム処理を選ぶ意味を説明します。
- [STANDARD-00000030：シーザー暗号](https://github.com/YusukeKato/ShellgeiOnlineJudge/blob/31d911ea34458dcb4e55cf35762be345d8ef28af/problems/v3/STANDARD-00000030.yaml)の参照解答は
  文字ごとの長い分岐ですが、文字集合の対応として考える余地があります。
  参照解答が長いことだけで題材の価値や難易度を決めず、自然な別解を探します。

これらは今後の設計判断の材料です。このガイドの追加を理由に既存問題を削除・改題したり、
参照解答をまとめて書き換えたりしません。
