import React, { useState } from "react";
import SojHeader from "./header";
import SojFooter from "./footer";
import SojInfo from "./info";
import SojAbout from "./about";
import SojContact from "./contact";
import SojOthers from "./others";
import SojSelectProblems from "./select_problems";
import SojSelected from "./selected";
import SojProblem from "./problem";
import SojRun from "./run";
import SojResult from "./result";
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
  /* SOJ param */
  const shellgei_limit: number = 1000;
  const default_image: string = soj_url + "/image/STANDARD-00000001.jpg";
  /* SOJ Info */
  const update_date: string = process.env.REACT_APP_UPDATE_DATE || "";
  const current_version: string = process.env.REACT_APP_VERSION || "";
  /* SOJ useState: select problem */
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
      <SojInfo update_date={update_date} current_version={current_version} />
      <SojAbout />
      <SojContact
        x_url={x_url}
        github_repository_url={github_repository_url}
        github_author_url={github_author_url}
        blog_url={blog_url}
        mixi2_url={mixi2_url}
      />
      <SojOthers />
      <SojSelectProblems
        soj_url={soj_url}
        selectedProblem={selectedProblem}
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
      <SojFooter />
    </div>
  );
};

export default App;
