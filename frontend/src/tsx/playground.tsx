import React, { useState } from "react";
import SojSelectProblems from "./select_problems";
import SojSelected from "./selected";
import SojProblem from "./problem";
import SojRun from "./run";
import SojResult from "./result";

interface PlaygroundProps {
  soj_url: string;
}

const Playground: React.FC<PlaygroundProps> = ({ soj_url }) => {
  const shellgei_limit: number = 1000;
  const default_image: string = soj_url + "/image/STANDARD-00000001.jpg";

  const [selectedProblem, setSelectedProblem] = useState("Select a problem.");
  const [problemStatement, setProblemStatement] = useState("Select a problem.");
  const [problemInput, setProblemInput] = useState("Select a problem.");
  const [problemOutput, setProblemOutput] = useState("Select a problem.");
  const [problemImage, setProblemImage] = useState(default_image);

  const [inputShellgei, setInputShellgei] = useState("");
  const changeInputShellgei = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputShellgei(event.target.value);
  };

  const [outputResult, setOutputResult] = useState("Run your shell-gei.");
  const [judgeResult, setJudgeResult] = useState("Run your shell-gei.");
  const [imageResult, setImageResult] = useState(default_image);
  const [userShellgeiStatus, setUserShellgeiStatus] = useState("Run your shell-gei.");

  return (
    <>
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
    </>
  );
};

export default Playground;