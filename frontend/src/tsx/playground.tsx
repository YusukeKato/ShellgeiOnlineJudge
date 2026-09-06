import React, { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiClientError } from "../api/client";
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
  const location = useLocation();
  const navigate = useNavigate();
  const problemParams = new URLSearchParams(location.search).getAll("problem");
  const requestedProblem = problemParams[0] ?? DEFAULT_PROBLEM_ID;
  // APIと同じID形式・上限に限定し、pathやqueryを詳細取得URLへ混入させない。
  const invalidProblem =
    problemParams.length > 1 ||
    requestedProblem.length > 64 ||
    !/^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$/.test(requestedProblem);
  const selectedProblem = invalidProblem ? DEFAULT_PROBLEM_ID : requestedProblem;
  const linkError = invalidProblem || location.state?.problemLinkInvalid === true;
  const changeProblemUrl = useCallback(
    (id: string, replace = false, invalidLink = false) => {
      // 問題以外のquery・fragmentを保ち、不正URLだけ履歴を増やさず置き換える。
      const params = new URLSearchParams(location.search);
      params.set("problem", id);
      navigate(
        { search: `?${params}`, hash: location.hash },
        {
          replace,
          state: { problemLinkInvalid: invalidLink },
        },
      );
    },
    [location.search, location.hash, navigate],
  );
  const [problem, setProblem] = useState<ProblemDisplay | null>(null);
  const [problemError, setProblemError] = useState<string | null>(null);
  const problemRequestVersion = useRef(0);
  const problemRequestController = useRef<AbortController | null>(null);

  useEffect(() => {
    if (invalidProblem) {
      changeProblemUrl(DEFAULT_PROBLEM_ID, true, true);
      return;
    }
    const problemId = selectedProblem;
    // abortを無視する古い応答でも、最新の選択内容を上書きしない。
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
      .catch((error: unknown) => {
        if (controller.signal.aborted || requestVersion !== problemRequestVersion.current) {
          return;
        }
        if (
          error instanceof ApiClientError &&
          error.status === 404 &&
          problemId !== DEFAULT_PROBLEM_ID
        ) {
          changeProblemUrl(DEFAULT_PROBLEM_ID, true, true);
          return;
        }
        console.error("Failed to get problem");
        setProblemError("Error: Failed to get problem");
      });
    // 履歴移動や画面破棄でも、古い詳細・404が最新の選択を上書きしない。
    return () => {
      problemRequestVersion.current += 1;
      controller.abort();
    };
  }, [soj_url, selectedProblem, invalidProblem, changeProblemUrl]);

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
            onSelectProblem={(id) => changeProblemUrl(id)}
          />
          {linkError && (
            <p role="alert" className="result-error" lang="en">
              Invalid or unknown problem in the URL. Showing STANDARD-00000001.
            </p>
          )}
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
