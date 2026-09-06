import React, { useCallback, useEffect, useRef, useState } from "react";
import { INITIAL_SUBMISSION_STATE, SubmissionState } from "../functions/submit";
import { ProblemDisplay, updateProblem } from "../functions/update_problem";
import SojSelectProblems from "./select_problems";
import SojProblem from "./problem";
import SojRun from "./run";
import SojResult from "./result";

interface PlaygroundProps {
  soj_url: string;
}

const DEFAULT_PROBLEM_ID = "STANDARD-00000001";

const Playground: React.FC<PlaygroundProps> = ({ soj_url }) => {
  // 通信と入力stateは言語に依存させず、表示だけを切り替える。
  const [selectedProblem, setSelectedProblem] = useState(DEFAULT_PROBLEM_ID);
  const [problem, setProblem] = useState<ProblemDisplay | null>(null);
  const [problemError, setProblemError] = useState<string | null>(null);
  const problemRequestVersion = useRef(0);
  const problemRequestController = useRef<AbortController | null>(null);

  const selectProblem = useCallback(
    (problemId: string) => {
      // abortを無視する古い応答でも、最新の選択内容を上書きしない。
      setSelectedProblem(problemId);
      setProblem(null);
      setProblemError(null);
      problemRequestController.current?.abort();
      const controller = new AbortController();
      problemRequestController.current = controller;
      const requestVersion = ++problemRequestVersion.current;
      void updateProblem(soj_url, problemId, controller.signal)
        .then((data) => {
          if (requestVersion === problemRequestVersion.current) {
            setProblem(data);
          }
        })
        .catch(() => {
          if (controller.signal.aborted || requestVersion !== problemRequestVersion.current) {
            return;
          }
          console.error("Failed to get problem");
          setProblemError("Error: Failed to get problem");
        });
    },
    [soj_url],
  );

  useEffect(() => {
    // 初期取得とURL変更時だけ再取得し、画面破棄時には保留中の通信を中断する。
    selectProblem(DEFAULT_PROBLEM_ID);
    return () => {
      problemRequestVersion.current += 1;
      problemRequestController.current?.abort();
    };
  }, [selectProblem]);

  const [inputShellgei, setInputShellgei] = useState("");
  const changeInputShellgei = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    // 問題や言語が変わっても入力を保持するため、workspaceで編集値を管理する。
    setInputShellgei(event.target.value);
  };
  const [submissionState, setSubmissionState] = useState<SubmissionState>(INITIAL_SUBMISSION_STATE);

  return (
    <div className="playground">
      <div className="workspace-grid">
        <div className="problem-column">
          <SojSelectProblems
            soj_url={soj_url}
            selectedProblem={selectedProblem}
            onSelectProblem={selectProblem}
          />
          <SojProblem problem={problem} error={problemError} selectedProblem={selectedProblem} />
        </div>
        <div className="workbench">
          <SojRun
            shellgei_limit={1000}
            soj_url={soj_url}
            inputShellgei={inputShellgei}
            changeInputShellgei={changeInputShellgei}
            selectedProblem={selectedProblem}
            submissionState={submissionState}
            setSubmissionState={setSubmissionState}
          />
          <SojResult submissionState={submissionState} />
        </div>
      </div>
    </div>
  );
};

export default Playground;
