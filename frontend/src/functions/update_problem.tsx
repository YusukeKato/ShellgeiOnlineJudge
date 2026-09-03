import { getProblem } from "../api/client";

export const updateProblem = async (
  soj_url: string,
  selectedProblem: string,
  setProblemStatement: (value: string) => void,
  setProblemInput: (value: string) => void,
  setProblemOutput: (value: string) => void,
  setProblemImage: (value: string) => void,
) => {
  // 選択IDの型検証済み問題詳細を取得し、問題文・入出力・画像URLを画面へ反映する。
  // 戻り値はなく、取得・契約検証に失敗した場合は各setterへfallback表示を設定する。
  try {
    const data = await getProblem(soj_url, selectedProblem);

    // 日本語と英語を結合
    const statementText =
      `${data.title_ja}\n${data.statement_ja}\n\n${data.title_en}\n${data.statement_en}`.trim();

    setProblemStatement(statementText || "NULL");
    setProblemInput(data.input || "NULL");
    setProblemOutput(data.expected_output || "NULL");
    setProblemImage(soj_url + data.image);
  } catch {
    console.error("Failed to get problem");
    setProblemStatement("Error: Failed to get problem");
    setProblemInput("Error: Failed to get problem");
    setProblemOutput("Error: Failed to get problem");
    setProblemImage(`${soj_url}/image/STANDARD-00000001.jpg`);
  }
};
