import { JudgeVerdict } from "../api/types";

export const judgeResult = (verdict: JudgeVerdict): string => {
  // v3の型付きverdictを既存の正解・不正解表示へ変換し、数字codeや部分一致に依存しない。
  if (verdict === "accepted") {
    return "正解 / Correct !!😄!!";
  }
  return "不正解 / Incorrect ...😭...";
};
