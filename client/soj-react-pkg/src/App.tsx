import React from "react";
import SojHeader from "./header";
import SojFooter from "./footer";
import SojNavList from "./nav_list";
import SojInfo from "./info";
import SojAbout from "./about";
import SojLogo from "./logo";
import "./App.css";
import "./common.css";
import SojNews from "./news";

const App: React.FC = () => {
  const x_url: string = "https://x.com/yusukekato_main";
  const github_url: string = "https://github.com/YusukeKato/ShellgeiOnlineJudge";
  const blog_url: string = "https://yusukekato.jp";
  const update_date: string = "2025/08/12";
  const current_version: string = "2.0.0";
  return (
    <div className="App">
      <header>
        <SojHeader />
      </header>
      <SojNavList x_url={x_url} github_url={github_url} blog_url={blog_url} />
      <SojInfo update_date={update_date} current_version={current_version} />
      <SojNews blog_url={blog_url} />
      <SojAbout />
      <SojLogo />
      <footer>
        <SojFooter />
      </footer>
    </div>
  );
};

export default App;
