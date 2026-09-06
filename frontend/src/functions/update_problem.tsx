import { getProblem } from "../api/client";

export interface ProblemDisplay {
  title: { ja: string; en: string };
  statement: { ja: string; en: string };
  input: string;
  output: string;
  image: string;
}

export const updateProblem = async (
  sojUrl: string,
  selectedProblem: string,
  signal: AbortSignal,
): Promise<ProblemDisplay> => {
  // 両言語を保持して取得し、表示言語の切替では通信や問題選択をやり直さない。
  // 取得失敗とabortは呼出側へ伝播し、世代管理下で画面へ反映する。
  const data = await getProblem(sojUrl, selectedProblem, { signal });
  return {
    title: { ja: data.title_ja, en: data.title_en },
    statement: { ja: data.statement_ja, en: data.statement_en },
    input: data.input || "NULL",
    output: data.expected_output || "NULL",
    image: sojUrl + data.image,
  };
};
