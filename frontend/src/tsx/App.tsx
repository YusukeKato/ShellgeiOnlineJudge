import React from "react";
import { BrowserRouter as Router, Routes, Route, NavLink } from "react-router-dom";
import SojHeader from "./header";
import SojFooter from "./footer";
import Playground from "./playground";
import AboutPage from "./about_page";
import "../css/App.css";
import "../css/common.css";
import "../css/nav.css";

const App: React.FC = () => {
  /* SOJ URLs */
  const x_url: string = import.meta.env.VITE_X_URL || "";
  const soj_url: string = import.meta.env.VITE_SOJ_URL || "";
  const github_repository_url: string = import.meta.env.VITE_GITHUB_REPO_URL || "";
  const github_author_url: string = import.meta.env.VITE_GITHUB_AUTHOR_URL || "";
  const blog_url: string = import.meta.env.VITE_BLOG_URL || "";
  const mixi2_url: string = import.meta.env.VITE_MIXI2_URL || "";

  /* SOJ Info */
  const update_date: string = import.meta.env.VITE_UPDATE_DATE || "";
  const current_version: string = import.meta.env.VITE_VERSION || "";

  return (
    <Router>
      <div className="App">
        <SojHeader />
        <nav className="main-nav">
          <NavLink
            to="/"
            className={({ isActive }) => (isActive ? "nav-button active" : "nav-button")}
            end
          >
            PLAYGROUND
          </NavLink>
          <NavLink
            to="/about"
            className={({ isActive }) => (isActive ? "nav-button active" : "nav-button")}
          >
            ABOUT & INFO
          </NavLink>
        </nav>
        <Routes>
          <Route path="/" element={<Playground soj_url={soj_url} />} />
          <Route
            path="/about"
            element={
              <AboutPage
                update_date={update_date}
                current_version={current_version}
                x_url={x_url}
                github_repository_url={github_repository_url}
                github_author_url={github_author_url}
                blog_url={blog_url}
                mixi2_url={mixi2_url}
              />
            }
          />
        </Routes>

        <SojFooter />
      </div>
    </Router>
  );
};

export default App;
