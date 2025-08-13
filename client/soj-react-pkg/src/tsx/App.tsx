import React from "react";
import SojHeader from "./header";
import SojFooter from "./footer";
import SojNavList from "./nav_list";
import SojInfo from "./info";
import SojNews from "./news";
import SojAbout from "./about";
import SojHistory from "./history";
import SojContact from "./contact";
import SojOthers from "./others";
import SojSelectStandard from "./select-standard";
import SojSelectPractice from "./select-practice";
import SojLogo from "./logo";
import "../css/App.css";
import "../css/common.css";

const App: React.FC = () => {
  const x_url: string = "https://x.com/yusukekato_main";
  const github_url: string = "https://github.com/YusukeKato/ShellgeiOnlineJudge";
  const github_author_url: string = "https://github.com/YusukeKato";
  const blog_url: string = "https://yusukekato.jp";
  const mixi2_url: string =
    "https://mixi.social/communities/dcf8e9d8-a6c4-40a9-8e05-328b4424f886/about";
  const update_date: string = "2025/08/12";
  const current_version: string = "2.0.0";
  return (
    <div className="App">
      <SojHeader />
      <SojNavList x_url={x_url} github_url={github_url} blog_url={blog_url} />
      <SojInfo update_date={update_date} current_version={current_version} />
      <SojNews blog_url={blog_url} />
      <SojAbout />
      <SojHistory />
      <SojContact
        x_url={x_url}
        github_url={github_url}
        github_author_url={github_author_url}
        blog_url={blog_url}
        mixi2_url={mixi2_url}
      />
      <SojOthers />
      <SojSelectStandard />
      <SojSelectPractice />
      <SojLogo />
      <SojFooter />
    </div>
  );
};

export default App;
