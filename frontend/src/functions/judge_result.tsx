import { JudgeReason, JudgeVerdict } from "../api/types";

// verdict追加時は表示の未定義を型検査で検出し、不正解への暗黙のfallbackを防ぐ。
const VERDICT_LABELS: Record<JudgeVerdict, string> = {
  accepted: "正解 / Correct !!😄!!",
  wrong_answer: "不正解 / Incorrect ...😭...",
  wrong_image: "不正解 / Incorrect ...😭...",
  wrong_text_and_image: "不正解 / Incorrect ...😭...",
  execution_failure: "実行失敗: コマンドの実行に失敗しました / Command execution failed",
  judge_error: "判定エラー: 判定処理でエラーが発生しました / Judging failed",
};

export const judgeResult = (verdict: JudgeVerdict, reason: JudgeReason | null): string => {
  // 検証済みverdictと安全なreason enumを固定文言へ変換し、内部詳細を表示に含めない。
  // exit codeやstatusから再判定せず、reason欠落時もverdictの失敗種別を維持する。
  if (verdict === "execution_failure") {
    switch (reason) {
      case "timed_out":
        return "実行失敗: 実行がタイムアウトしました / Execution timed out";
      case "output_truncated":
        return "実行失敗: 出力上限を超えました / Output limit exceeded";
      case "non_zero_exit":
        return "実行失敗: コマンドが非0の終了コードで終了しました / Command exited with a non-zero status";
      case "stderr_not_empty":
        return "実行失敗: 許可されていない標準エラー出力がありました / Standard error output is not allowed";
    }
  }
  return VERDICT_LABELS[verdict];
};
