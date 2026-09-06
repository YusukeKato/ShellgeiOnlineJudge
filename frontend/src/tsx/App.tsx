import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { LanguageProvider, useLanguage } from "../language";
import { REPOSITORY_URL } from "../links";
import SojHeader from "./header";
import SojFooter from "./footer";
import Playground from "./playground";
import AboutPage from "./about_page";
import "../css/design.css";

// 共通の言語context内で画面を構成し、言語変更ではrouteを作り直さない。
const AppLayout: React.FC = () => {
  const { text } = useLanguage();
  const soj_url: string = import.meta.env.VITE_SOJ_URL || "";

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        {text("本文へ移動", "Skip to content")}
      </a>
      <SojHeader />
      <main id="main-content" tabIndex={-1}>
        <Routes>
          <Route path="/" element={<Playground soj_url={soj_url} />} />
          <Route
            path="/about"
            element={
              <AboutPage
                update_date={import.meta.env.VITE_UPDATE_DATE || ""}
                current_version={__APP_VERSION__}
                x_url={import.meta.env.VITE_X_URL || ""}
                github_repository_url={REPOSITORY_URL}
                github_author_url={import.meta.env.VITE_GITHUB_AUTHOR_URL || ""}
                blog_url={import.meta.env.VITE_BLOG_URL || ""}
                mixi2_url={import.meta.env.VITE_MIXI2_URL || ""}
              />
            }
          />
        </Routes>
      </main>
      <SojFooter />
    </div>
  );
};

// 言語設定を全routeで共有し、外部サービスへの通信なしで表示を切り替える。
const App: React.FC = () => (
  <LanguageProvider>
    <Router>
      <AppLayout />
    </Router>
  </LanguageProvider>
);

export default App;
