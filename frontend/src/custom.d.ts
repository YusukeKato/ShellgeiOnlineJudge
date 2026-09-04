declare module "*.jpg";
declare module "*.jpeg";
declare module "*.png";
declare module "*.svg";
declare module "*.gif";

interface ImportMetaEnv {
  readonly VITE_SOJ_URL?: string;
  readonly VITE_UPDATE_DATE?: string;
  readonly VITE_VERSION?: string;
  readonly VITE_X_URL?: string;
  readonly VITE_GITHUB_REPO_URL?: string;
  readonly VITE_GITHUB_AUTHOR_URL?: string;
  readonly VITE_BLOG_URL?: string;
  readonly VITE_MIXI2_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
