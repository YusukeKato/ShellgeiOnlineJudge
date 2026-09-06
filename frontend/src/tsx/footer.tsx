import React from "react";
import { Link } from "react-router-dom";
import { useLanguage } from "../language";
import { CONTACT_FORM_URL, REPOSITORY_URL } from "../links";

// 利用案内・問い合わせ・製品versionを全画面の末尾から確認できるようにする。
const SojFooter: React.FC = () => {
  const { text } = useLanguage();

  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <div>
          <span className="version-label">Shellgei Online Judge · v{__APP_VERSION__}</span>
          <p className="muted">&copy; 2023 YusukeKato All rights reserved.</p>
        </div>
        <nav className="footer-links" aria-label={text("関連リンク", "Related links")}>
          <Link to="/about">{text("使い方・情報", "About")}</Link>
          <a href={CONTACT_FORM_URL} target="_blank" rel="noopener noreferrer">
            {text("お問い合わせ", "Contact")}
            <span aria-hidden="true"> ↗</span>
            <span className="visually-hidden">
              {text("（別タブで開きます）", " (opens in a new tab)")}
            </span>
          </a>
          <a href={REPOSITORY_URL} target="_blank" rel="noopener noreferrer">
            GitHub
            <span aria-hidden="true"> ↗</span>
            <span className="visually-hidden">
              {text("（別タブで開きます）", " (opens in a new tab)")}
            </span>
          </a>
        </nav>
      </div>
    </footer>
  );
};

export default SojFooter;
