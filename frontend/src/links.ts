// 共通の外部リンクはヘッダー・フッター・案内画面で同じ行き先を使用する。
export const CONTACT_FORM_URL =
  "https://docs.google.com/forms/d/e/1FAIpQLSe8XIueiVyEXZBlVzwTYzqF241MLRkYK17PCtKy8Y94Fs7z1A/viewform?usp=dialog";

export const REPOSITORY_URL = (
  import.meta.env.VITE_GITHUB_REPO_URL || "https://github.com/YusukeKato/ShellgeiOnlineJudge"
).replace(/\/+$/, "");
