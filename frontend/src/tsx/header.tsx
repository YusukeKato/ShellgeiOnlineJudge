import React from "react";
import { Link, NavLink } from "react-router-dom";
import { useLanguage } from "../language";
import blueTreeIcon from "../images/BlueTreeIcon.jpg";

// ページ移動と表示言語を共通ヘッダーへまとめ、スマートフォンでも直接操作できるようにする。
const SojHeader: React.FC = () => {
  const { language, setLanguage, text } = useLanguage();

  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="brand" to="/" aria-label="Shellgei Online Judge">
          <img className="brand-mark" src={blueTreeIcon} width={36} height={36} alt="" />
          <span className="brand-name">
            Shellgei <span>Online Judge</span>
          </span>
        </Link>
        <nav className="site-nav" aria-label={text("メインナビゲーション", "Main navigation")}>
          <NavLink className="nav-link" to="/" end>
            {text("問題を解く", "Playground")}
          </NavLink>
          <NavLink className="nav-link" to="/about">
            {text("使い方・情報", "About")}
          </NavLink>
        </nav>
        <div className="language-switch" role="group" aria-label={text("表示言語", "Language")}>
          <button
            type="button"
            lang="ja"
            aria-pressed={language === "ja"}
            onClick={() => setLanguage("ja")}
          >
            日本語
          </button>
          <button
            type="button"
            lang="en"
            aria-pressed={language === "en"}
            onClick={() => setLanguage("en")}
          >
            English
          </button>
        </div>
      </div>
    </header>
  );
};

export default SojHeader;
