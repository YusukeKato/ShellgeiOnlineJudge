import React, { useCallback, useEffect, useRef, useState } from "react";
import { INITIAL_SUBMISSION_STATE, SubmissionState } from "../functions/submit";
import { updateProblem } from "../functions/update_problem";
import SojSelectProblems from "./select_problems";
import SojSelected from "./selected";
import SojProblem from "./problem";
import SojRun from "./run";
import SojResult from "./result";

interface PlaygroundProps {
  soj_url: string;
}

const DEFAULT_PROBLEM_ID = "STANDARD-00000001";

const Playground: React.FC<PlaygroundProps> = ({ soj_url }) => {
  const shellgei_limit: number = 1000;
  const default_image: string = soj_url + `/image/${DEFAULT_PROBLEM_ID}.jpg`;

  const [selectedProblem, setSelectedProblem] = useState(DEFAULT_PROBLEM_ID);
  const [problemStatement, setProblemStatement] = useState("Loading problem...");
  const [problemInput, setProblemInput] = useState("Loading problem...");
  const [problemOutput, setProblemOutput] = useState("Loading problem...");
  const [problemImage, setProblemImage] = useState(default_image);
  const problemRequestVersion = useRef(0);
  const problemRequestController = useRef<AbortController | null>(null);

  const selectProblem = useCallback(
    (problemId: string) => {
      // 前回の問題詳細取得を中断し、世代番号が最新のresponseだけを問題表示へ反映する。
      setSelectedProblem(problemId);
      problemRequestController.current?.abort();
      const controller = new AbortController();
      problemRequestController.current = controller;
      const requestVersion = ++problemRequestVersion.current;
      void updateProblem(soj_url, problemId, controller.signal)
        .then((problem) => {
          // fetch mock等がabortを無視して完了しても、古いresponseで最新選択を上書きしない。
          if (requestVersion !== problemRequestVersion.current) {
            return;
          }
          setProblemStatement(problem.statement);
          setProblemInput(problem.input);
          setProblemOutput(problem.output);
          setProblemImage(problem.image);
        })
        .catch(() => {
          // 中断した旧requestは表示を変更せず、最新requestの失敗だけをfallbackへ変換する。
          if (controller.signal.aborted || requestVersion !== problemRequestVersion.current) {
            return;
          }
          console.error("Failed to get problem");
          setProblemStatement("Error: Failed to get problem");
          setProblemInput("Error: Failed to get problem");
          setProblemOutput("Error: Failed to get problem");
          setProblemImage(default_image);
        });
    },
    [default_image, soj_url],
  );

  useEffect(() => {
    // 初回表示時に標準問題1番の詳細を取得し、初期選択IDに対応する問題文と入出力を表示する。
    selectProblem(DEFAULT_PROBLEM_ID);
    return () => {
      // URL変更またはunmount時に進行中の問題取得を中断し、遅延responseのstate更新を防ぐ。
      problemRequestVersion.current += 1;
      problemRequestController.current?.abort();
    };
  }, [selectProblem]);

  const [inputShellgei, setInputShellgei] = useState("");
  const changeInputShellgei = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputShellgei(event.target.value);
  };

  const [submissionState, setSubmissionState] = useState<SubmissionState>(INITIAL_SUBMISSION_STATE);

  return (
    <>
      <SojSelectProblems
        soj_url={soj_url}
        selectedProblem={selectedProblem}
        onSelectProblem={selectProblem}
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
        soj_url={soj_url}
        inputShellgei={inputShellgei}
        changeInputShellgei={changeInputShellgei}
        selectedProblem={selectedProblem}
        submissionState={submissionState}
        setSubmissionState={setSubmissionState}
      />
      <SojResult submissionState={submissionState} defaultImage={default_image} />
    </>
  );
};

export default Playground;
