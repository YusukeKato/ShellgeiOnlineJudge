import React, { useState } from "react";
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
import SojSelectImage from "./select-image";
import SojSelected from "./selected";
import SojProblem from "./problem";
import SojRun from "./run";
import SojResult from "./result";
import SojLogo from "./logo";
import "../css/App.css";
import "../css/common.css";

const App: React.FC = () => {
  /* SOJ URLs */
  const x_url: string = "https://x.com/yusukekato_main";
  const soj_url: string = "https://shellgei-online-judge.com";
  // const soj_url: string = "http://localhost";
  const github_repository_url: string = "https://github.com/YusukeKato/ShellgeiOnlineJudge";
  const github_author_url: string = "https://github.com/YusukeKato";
  const blog_url: string = "https://yusukekato.jp";
  const mixi2_url: string =
    "https://mixi.social/communities/dcf8e9d8-a6c4-40a9-8e05-328b4424f886/about";

  /* SOJ param */
  const shellgei_limit: number = 1000;
  const default_image: string = soj_url + "/image/GENERAL-00000001.jpg";

  /* SOJ Info */
  const update_date: string = "2025/09/06";
  const current_version: string = "2.2.0";

  /* SOJ useState: select problem */
  const [selectedProblemStandard, setSelectedProblemStandard] = useState("GENERAL-00000001");
  const changeSelectedProblemStandard = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedProblemStandard(event.target.value);
  };
  const [selectedProblemPractice, setSelectedProblemPractice] = useState("EXERCISE-awk-01");
  const changeSelectedProblemPractice = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedProblemPractice(event.target.value);
  };
  const [selectedProblemImage, setSelectedProblemImage] = useState("IMAGE-00000001");
  const changeSelectedProblemImage = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedProblemImage(event.target.value);
  };
  const [selectedProblem, setSelectedProblem] = useState("Select a problem.");

  /* SOJ useState: get problem */
  const [problemStatement, setProblemStatement] = useState("Select a problem.");
  const [problemInput, setProblemInput] = useState("Select a problem.");
  const [problemOutput, setProblemOutput] = useState("Select a problem.");
  const [problemImage, setProblemImage] = useState(default_image);

  /* SOJ useState: input shellgei */
  const [inputShellgei, setInputShellgei] = useState("");
  const changeInputShellgei = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputShellgei(event.target.value);
  };

  /* SOJ useState: result */
  const [outputResult, setOutputResult] = useState("Run your shell-gei.");
  const [judgeResult, setJudgeResult] = useState("Run your shell-gei.");
  const [imageResult, setImageResult] = useState(default_image);
  const [userShellgeiStatus, setUserShellgeiStatus] = useState("Run your shell-gei.");

  return (
    <div className="App">
      <SojHeader />
      <SojNavList x_url={x_url} github_repository_url={github_repository_url} blog_url={blog_url} />
      <SojInfo update_date={update_date} current_version={current_version} />
      <SojNews blog_url={blog_url} />
      <SojAbout />
      <SojHistory />
      <SojContact
        x_url={x_url}
        github_repository_url={github_repository_url}
        github_author_url={github_author_url}
        blog_url={blog_url}
        mixi2_url={mixi2_url}
      />
      <SojOthers />
      <SojSelectStandard
        soj_url={soj_url}
        selectedProblemStandard={selectedProblemStandard}
        changeSelectedProblemStandard={changeSelectedProblemStandard}
        setSelectedProblem={setSelectedProblem}
        setProblemStatement={setProblemStatement}
        setProblemInput={setProblemInput}
        setProblemOutput={setProblemOutput}
        setProblemImage={setProblemImage}
      />
      <SojSelectPractice
        soj_url={soj_url}
        selectedProblemPractice={selectedProblemPractice}
        changeSelectedProblemPractice={changeSelectedProblemPractice}
        setSelectedProblem={setSelectedProblem}
        setProblemStatement={setProblemStatement}
        setProblemInput={setProblemInput}
        setProblemOutput={setProblemOutput}
        setProblemImage={setProblemImage}
      />
      <SojSelectImage
        soj_url={soj_url}
        selectedProblemImage={selectedProblemImage}
        changeSelectedProblemImage={changeSelectedProblemImage}
        setSelectedProblem={setSelectedProblem}
        setProblemStatement={setProblemStatement}
        setProblemInput={setProblemInput}
        setProblemOutput={setProblemOutput}
        setProblemImage={setProblemImage}
      />
      <SojSelected selectedProblem={selectedProblem} />
      <SojProblem
        problemStatement={problemStatement}
        problemInput={problemInput}
        problemOutput={problemOutput}
        problemImage={problemImage}
      />
      <SojRun
        shellgei_limit={shellgei_limit}
        default_image={default_image}
        soj_url={soj_url}
        inputShellgei={inputShellgei}
        changeInputShellgei={changeInputShellgei}
        selectedProblem={selectedProblem}
        setOutputResult={setOutputResult}
        setJudgeResult={setJudgeResult}
        setImageResult={setImageResult}
        setUserShellgeiStatus={setUserShellgeiStatus}
      />
      <SojResult
        outputResult={outputResult}
        judgeResult={judgeResult}
        imageResult={imageResult}
        userShellgeiStatus={userShellgeiStatus}
      />
      <SojLogo />
      <SojFooter />
    </div>
  );
};

export default App;
