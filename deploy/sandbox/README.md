# シェル芸オンラインジャッジ用sandbox

公式 **Ubuntu 24.04** をベースに、コマンド実行用のツール・データ・設定を追加します。
ベースイメージのdigestとパッケージ一覧は[Dockerfile](./Dockerfile)を参照してください。

## 収録するもの

| 用途 | 追加・設定内容 |
| --- | --- |
| シェル・基本操作 | Bash、GNU coreutils、tar |
| テキスト・ファイル処理 | GNU awk、grep、sed、find、xargs |
| 計算・整形 | bc、rs |
| 画像生成 | ImageMagick 6、[textimg](https://github.com/jiro4989/textimg) |
| 日本語対応 | ja_JP.UTF-8ロケール、Noto CJKフォント |
| 公開データ | [ShellGeiData](https://github.com/ryuichiueda/ShellGeiData)全体を`/ShellGeiData`へ配置（`.git`を除く） |

ShellGeiDataはビルドごとにdefault branchの最新commitを確認・取得し、
commit IDを`/usr/local/share/soj/shellgeidata-revision`へ記録します。

textimgは専用のGoビルドstageで静的ビルドし、実行ファイルとライセンスを収録します。
依存バージョンは[textimg/go.mod](./textimg/go.mod)・[go.sum](./textimg/go.sum)で固定します。

## イメージ内の設定

- Ubuntuパッケージの更新を適用し、推奨パッケージを省いてインストール。
- 通常ファイルのsetuid/setgid属性を除去。
- ImageMagickの外部処理・画像形式・資源使用量を[policy.xml](./policy.xml)で制限。
- 作業ディレクトリを`/work`、`SHELL`を`/bin/bash`に設定。

ビルドにはBuildKit対応のDockerを使用します。Ubuntuパッケージの更新を再取得する場合は
`--no-cache`を指定します。ビルド・検証・更新手順は[本番運用](../../docs/PRODUCTION.md#sandbox専用image)、
runnerが適用するネットワーク隔離・資源制限は[SECURITY.md](../../SECURITY.md#sandboxコンテナの設定)を参照してください。
