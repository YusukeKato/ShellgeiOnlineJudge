import { ApiClientError, submitSolution } from "../api/client";
import { ExecutionResultV3 } from "../api/types";
import { escapeShellgei } from "./escape_str";
import { judgeResult } from "./judge_result";

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
    return error.kind === "timeout" ? error.message : `Error: ${error.message}`;
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

export const submit = async (
  shellgei_limit: number,
  default_image: string,
  soj_url: string,
  shellgei: string,
  selectedProblem: string,
  setOutputResult: (value: string) => void,
  setJudgeResult: (value: string) => void,
  setImageResult: (value: string) => void,
  setUserShellgeiStatus: (value: string) => void,
) => {
  // 入力長を検査してv3 APIへ提出し、型付き判定・実行結果・artifactを既存画面へ反映する。
  // 戻り値はなく、通信失敗時も各setterへ安全なerror表示と既定画像を設定する。
  if (shellgei.length === 0) {
    setOutputResult("No input provided");
    setJudgeResult("No input provided");
    setImageResult(default_image);
  } else if (shellgei.length <= shellgei_limit) {
    setOutputResult("Running...");
    setJudgeResult("Running...");
    setImageResult(default_image);
    shellgei = escapeShellgei(shellgei);
    try {
      const response = await submitSolution(soj_url, {
        shellgei,
        problem_id: selectedProblem,
      });
      setOutputResult(executionOutput(response.execution));
      setJudgeResult(judgeResult(response.verdict));
      setUserShellgeiStatus(
        "SHELLGEI ID: " +
          (response.submission_id ?? "not saved") +
          "\nDATE: " +
          response.submitted_at +
          "\nYOUR SHELLGEI: " +
          shellgei,
      );
      const imageUrl =
        response.artifact === null
          ? null
          : imageDataUrl(response.artifact.data, response.artifact.media_type);
      setImageResult(imageUrl ?? default_image);
    } catch (error: unknown) {
      console.error("Failed to post shellgei");
      const errorMessage = submissionErrorMessage(error);
      setOutputResult(errorMessage);
      setJudgeResult(errorMessage);
      setUserShellgeiStatus(errorMessage);
      setImageResult(default_image);
    }
  } else {
    setOutputResult("Exceeded character limit:" + shellgei_limit.toString());
    setJudgeResult("Exceeded character limit:" + shellgei_limit.toString());
    setUserShellgeiStatus("Exceeded character limit:" + shellgei_limit.toString());
    setImageResult(default_image);
  }
};
