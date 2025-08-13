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
import SojLogo from "./logo";
import "../css/App.css";
import "../css/common.css";

const App: React.FC = () => {
  const x_url: string = "https://x.com/yusukekato_main";
  // const soj_url: string = "https://shellgei-online-judge.com";
  const soj_url: string = "http://localhost";
  const github_url: string = "https://github.com/YusukeKato/ShellgeiOnlineJudge";
  const github_author_url: string = "https://github.com/YusukeKato";
  const blog_url: string = "https://yusukekato.jp";
  const mixi2_url: string =
    "https://mixi.social/communities/dcf8e9d8-a6c4-40a9-8e05-328b4424f886/about";
  const update_date: string = "2025/08/12";
  const current_version: string = "2.0.0";

  const [selectedValueStandard, setSelectedValueStandard] = useState("GENERAL-00000001");
  const handleSelectChangeStandard = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedValueStandard(event.target.value);
  };
  const [selectedValuePractice, setSelectedValuePractice] = useState("EXERCISE-awk-01");
  const handleSelectChangePractice = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedValuePractice(event.target.value);
  };
  const [selectedValueImage, setSelectedValueImage] = useState("IMAGE-00000001");
  const handleSelectChangeImage = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedValueImage(event.target.value);
  };
  const [selectedProblem, setSelectedProblem] = useState("Select a problem.");

  const [problemStatement, setProblemStatement] = useState("Select a problem.");
  const [problemInput, setProblemInput] = useState("Select a problem.");
  const [problemOutput, setProblemOutput] = useState("Select a problem.");

  const [inputShellgei, setInputShellgei] = useState("");
  const handleInputShellgeiChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputShellgei(event.target.value);
  };

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
      <SojSelectStandard
        soj_url={soj_url}
        selectedValue={selectedValueStandard}
        handleSelectChange={handleSelectChangeStandard}
        setSelectedProblem={setSelectedProblem}
        setProblemStatement={setProblemStatement}
        setProblemInput={setProblemInput}
        setProblemOutput={setProblemOutput}
      />
      <SojSelectPractice
        soj_url={soj_url}
        selectedValue={selectedValuePractice}
        handleSelectChange={handleSelectChangePractice}
        setSelectedProblem={setSelectedProblem}
        setProblemStatement={setProblemStatement}
        setProblemInput={setProblemInput}
        setProblemOutput={setProblemOutput}
      />
      <SojSelectImage
        soj_url={soj_url}
        selectedValue={selectedValueImage}
        handleSelectChange={handleSelectChangeImage}
        setSelectedProblem={setSelectedProblem}
        setProblemStatement={setProblemStatement}
        setProblemInput={setProblemInput}
        setProblemOutput={setProblemOutput}
      />
      <SojSelected selectedValue={selectedProblem} />
      <SojProblem
        problemStatement={problemStatement}
        problemInput={problemInput}
        problemOutput={problemOutput}
      />
      <SojRun inputShellgei={inputShellgei} handleInputShellgeiChange={handleInputShellgeiChange} />
      <SojLogo />
      <SojFooter />
    </div>
  );
};

export default App;
