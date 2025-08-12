import React from "react";
import SojHeader from "./header";
import SojFooter from "./footer";
import SojNavList from "./nav_list";
import SojLogo from "./logo";
import "./App.css";
import "./common.css";

const App: React.FC = () => {
  const x_url: string = "https://x.com/yusukekato_main";
  const github_url: string = "https://github.com/YusukeKato/ShellgeiOnlineJudge";
  const blog_url: string = "https://yusukekato.jp";
  return (
    <div className="App">
      <header>
        <SojHeader />
      </header>
      <div className="soj-centering">
        <div className="soj-main">
          <SojNavList x_url={x_url} github_url={github_url} blog_url={blog_url} />
          <SojLogo />
        </div>
      </div>
      <footer>
        <SojFooter />
      </footer>
    </div>
  );
};

export default App;
