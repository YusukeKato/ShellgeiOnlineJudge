import { JudgeReason, JudgeVerdict } from "../api/types";
import { Language } from "../language";

// 判定追加は型検査で検出する。エラーの詳細は両言語で安全な固定英文を使用する。
const VERDICT_LABELS: Record<Language, Record<JudgeVerdict, string>> = {
  ja: {
    accepted: "正解",
    wrong_answer: "不正解",
    wrong_image: "不正解",
    wrong_text_and_image: "不正解",
    execution_failure: "Execution failed: Command execution failed",
    judge_error: "Judge error: Judging failed",
  },
  en: {
    accepted: "Accepted",
    wrong_answer: "Wrong answer",
    wrong_image: "Wrong answer",
    wrong_text_and_image: "Wrong answer",
    execution_failure: "Execution failed: Command execution failed",
    judge_error: "Judge error: Judging failed",
  },
};

export const judgeResult = (
  verdict: JudgeVerdict,
  reason: JudgeReason | null,
  language: Language = "ja",
): string => {
  // APIの判定を表示へ変換し、実行statusから独自に再判定しない。内部reasonは公開しない。
  if (verdict === "execution_failure") {
    switch (reason) {
      case "timed_out":
        return "Execution failed: Execution timed out";
      case "output_truncated":
        return "Execution failed: Output limit exceeded";
      case "non_zero_exit":
        return "Execution failed: Command exited with a non-zero status";
      case "stderr_not_empty":
        return "Execution failed: Standard error output is not allowed";
    }
  }
  return VERDICT_LABELS[language][verdict];
};
