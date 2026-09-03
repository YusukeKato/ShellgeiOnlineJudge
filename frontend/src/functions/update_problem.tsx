import { getProblem } from "../api/client";

export interface ProblemDisplay {
  statement: string;
  input: string;
  output: string;
  image: string;
}

export const updateProblem = async (
  sojUrl: string,
  selectedProblem: string,
  signal: AbortSignal,
): Promise<ProblemDisplay> => {
  // 選択IDの型検証済み問題詳細を取得し、画面用の問題文・入出力・画像URLを返す。
  // 呼出側signalのabortや取得失敗は伝播し、最新requestかを判定する呼出側だけがstateを更新する。
  const data = await getProblem(sojUrl, selectedProblem, { signal });
  const statement =
    `${data.title_ja}\n${data.statement_ja}\n\n${data.title_en}\n${data.statement_en}`.trim();
  return {
    statement: statement || "NULL",
    input: data.input || "NULL",
    output: data.expected_output || "NULL",
    image: sojUrl + data.image,
  };
};
