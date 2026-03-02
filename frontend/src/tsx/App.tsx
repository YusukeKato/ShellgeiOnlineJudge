import React from "react";
import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
import SojHeader from "./header";
import SojFooter from "./footer";
import Playground from "./playground";
import AboutPage from "./about_page";
import "../css/App.css";
import "../css/common.css";

const App: React.FC = () => {
  /* SOJ URLs */
  const x_url: string = process.env.REACT_APP_X_URL || "";
  const soj_url: string = process.env.REACT_APP_SOJ_URL || "";
  const github_repository_url: string = process.env.REACT_APP_GITHUB_REPO_URL || "";
  const github_author_url: string = process.env.REACT_APP_GITHUB_AUTHOR_URL || "";
  const blog_url: string = process.env.REACT_APP_BLOG_URL || "";
  const mixi2_url: string = process.env.REACT_APP_MIXI2_URL || "";

  /* SOJ Info */
  const update_date: string = process.env.REACT_APP_UPDATE_DATE || "";
  const current_version: string = process.env.REACT_APP_VERSION || "";

  return (
    <Router>
      <div className="App">
        <SojHeader />
        <nav style={{ textAlign: "center", margin: "1.5rem 0" }}>
          <Link
            to="/"
            style={{
              margin: "0 1rem",
              fontWeight: "bold",
              color: "#007acc",
              textDecoration: "none",
              fontSize: "1.1rem",
            }}
          >
            PLAYGROUND
          </Link>
          <Link
            to="/about"
            style={{
              margin: "0 1rem",
              fontWeight: "bold",
              color: "#007acc",
              textDecoration: "none",
              fontSize: "1.1rem",
            }}
          >
            ABOUT & INFO
          </Link>
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
