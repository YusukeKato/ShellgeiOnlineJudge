declare module "*.jpg";
declare module "*.jpeg";
declare module "*.png";
declare module "*.svg";
declare module "*.gif";

interface ImportMetaEnv {
  readonly VITE_SOJ_URL?: string;
  readonly VITE_UPDATE_DATE?: string;
  readonly VITE_X_URL?: string;
  readonly VITE_GITHUB_REPO_URL?: string;
  readonly VITE_GITHUB_AUTHOR_URL?: string;
  readonly VITE_BLOG_URL?: string;
  readonly VITE_MIXI2_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// 製品versionはViteが正本から埋め込み、環境変数に依存させない。
declare const __APP_VERSION__: string;
