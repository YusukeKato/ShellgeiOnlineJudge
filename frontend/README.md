# SHELLGEI ONLINE JUDGE: frontend
This repository is the webapp frontend for SHELLGEI ONLINE JUDGE.

## Environment
- React
- TypeScript

## Install

Node.js 22とYarnを使用します。
環境構築全体は[開発環境の構築・テスト・起動](../docs/DEVELOPMENT.md)を参照してください。

```sh
cd frontend
yarn install --frozen-lockfile
```

## build

```sh
yarn format:check
yarn lint
CI=true yarn test --watchAll=false
yarn build
```

## 参考
下記記事を参考にさせていただきました。

- nodejs and npm: https://qiita.com/nouernet/items/d6ad4d5f4f08857644de
- yarn and react: https://qiita.com/NaoyaOgura/items/cb94fefb6a63b7965f15
- nginx + react: https://www.yoheim.net/blog.php?q=20180407
