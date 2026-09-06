import { ApiClientError, submitSolution } from "../api/client";
import { ExecutionResultV3, SubmissionResponseV3 } from "../api/types";
import { escapeShellgei } from "./escape_str";
import { judgeResult } from "./judge_result";
import { Language } from "../language";

export interface IdleSubmissionState {
  kind: "idle";
}

export interface RunningSubmissionState {
  kind: "running";
  requestKey: string;
  shellgei: string;
  problemId: string;
}

export interface SucceededSubmissionState {
  kind: "succeeded";
  shellgei: string;
  problemId: string;
  response: SubmissionResponseV3;
}

export interface FailedSubmissionState {
  kind: "failed";
  message: string;
}

export interface ValidationErrorSubmissionState {
  kind: "validation_error";
  message: string;
}

export type SubmissionState =
  | IdleSubmissionState
  | RunningSubmissionState
  | SucceededSubmissionState
  | FailedSubmissionState
  | ValidationErrorSubmissionState;

export type SubmissionTerminalState =
  | SucceededSubmissionState
  | FailedSubmissionState
  | ValidationErrorSubmissionState;

export interface SubmissionDisplay {
  output: string;
  verdict: string;
  image: string | null;
  commandStatus: string;
}

export const INITIAL_SUBMISSION_STATE: IdleSubmissionState = { kind: "idle" };

const executionOutput = (execution: ExecutionResultV3): string => {
  // v3の分離stdout・stderrと実行statusを、従来画面の単一出力欄へ明示的にmappingする。
  const output = execution.stdout + execution.stderr;
  if (execution.status === "timed_out") {
    return `${output}\n[Timed out]`;
  }
  if (execution.status === "output_limit") {
    return `${output}...`;
  }
  if (execution.status === "error") {
    return "Error during execution";
  }
  return output;
};

const submissionErrorMessage = (error: unknown): string => {
  // API clientの安全な分類済みmessageを画面用に返し、未知例外の内部情報は公開しない。
  if (error instanceof ApiClientError) {
    return error.kind === "timeout" || error.kind === "aborted"
      ? error.message
      : `Error: ${error.message}`;
  }
  return "Error: Failed to submit solution";
};

export const imageDataUrl = (image: string, mediaType: string): string | null => {
  // Base64画像と許可済みJPEG/GIF MIMEからdata URLを作り、不正MIMEならnullを返す。
  if (mediaType !== "image/jpeg" && mediaType !== "image/gif") {
    return null;
  }
  return `data:${mediaType};base64,${image}`;
};

export const prepareSubmission = (
  shellgeiLimit: number,
  shellgei: string,
  selectedProblem: string,
): RunningSubmissionState | ValidationErrorSubmissionState => {
  // 入力commandを正規化して長さを検査し、送信可能なrunning stateまたは検証errorを返す。
  // 同一problem・commandから作るrequestKeyは二重送信の判定に使用する。
  if (shellgei.length === 0) {
    return { kind: "validation_error", message: "No input provided" };
  }
  if (shellgei.length > shellgeiLimit) {
    return {
      kind: "validation_error",
      message: `Exceeded character limit:${shellgeiLimit}`,
    };
  }
  const normalizedShellgei = escapeShellgei(shellgei);
  return {
    kind: "running",
    requestKey: `${selectedProblem}\u0000${normalizedShellgei}`,
    shellgei: normalizedShellgei,
    problemId: selectedProblem,
  };
};

export const submit = async (
  sojUrl: string,
  submission: RunningSubmissionState,
  signal: AbortSignal,
): Promise<SubmissionTerminalState> => {
  // running stateをv3 APIへ送り、成功responseまたは分類済み失敗stateを返す。
  // 入力signalがabortされた場合は実通信も中断し、利用者dataをconsoleへ出力しない。
  try {
    const response = await submitSolution(
      sojUrl,
      {
        shellgei: submission.shellgei,
        problem_id: submission.problemId,
      },
      { signal },
    );
    return {
      kind: "succeeded",
      shellgei: submission.shellgei,
      problemId: submission.problemId,
      response,
    };
  } catch (error: unknown) {
    if (!(error instanceof ApiClientError) || error.kind !== "aborted") {
      console.error("Failed to post shellgei");
    }
    return { kind: "failed", message: submissionErrorMessage(error) };
  }
};

export const submissionDisplay = (
  state: SubmissionState,
  language: Language = "ja",
): SubmissionDisplay => {
  // 保存済みのstateを表示時の言語で変換する。エラーは英文を保ち、存在しない画像は返さない。
  if (state.kind === "idle") {
    return {
      output: "Output will be displayed here.",
      verdict: language === "ja" ? "未実行" : "Not run yet",
      image: null,
      commandStatus: "Executed command will be displayed here.",
    };
  }
  if (state.kind === "running") {
    return {
      output: "Running...",
      verdict: language === "ja" ? "実行中…" : "Running…",
      image: null,
      commandStatus: `Running ${state.problemId}...`,
    };
  }
  if (state.kind === "failed" || state.kind === "validation_error") {
    return {
      output: state.message,
      verdict: state.message,
      image: null,
      commandStatus: state.message,
    };
  }
  const artifact = state.response.artifact;
  const image = artifact === null ? null : imageDataUrl(artifact.data, artifact.media_type);
  return {
    output: executionOutput(state.response.execution),
    verdict: judgeResult(state.response.verdict, state.response.reason, language),
    image,
    commandStatus:
      (language === "ja" ? "提出ID: " : "Submission ID: ") +
      (state.response.submission_id ?? "—") +
      (language === "ja" ? "\n日時: " : "\nDate: ") +
      state.response.submitted_at +
      (language === "ja" ? "\nコマンド: " : "\nCommand: ") +
      state.shellgei,
  };
};
