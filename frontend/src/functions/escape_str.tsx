export const escapeHtml = (text: string): string => {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
};

export const escapeShellgei = (text: string): string => {
  return text.replace(/\r/g, "").trim().replace(/\n$/g, "");
};
