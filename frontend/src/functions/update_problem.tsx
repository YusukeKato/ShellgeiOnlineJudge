export const updateProblem = async (
  soj_url: string,
  selectedProblem: string,
  setProblemStatement: (value: string) => void,
  setProblemInput: (value: string) => void,
  setProblemOutput: (value: string) => void,
  setProblemImage: (value: string) => void,
) => {
  try {
    const api_endpoint = `${soj_url}/api/problems/${selectedProblem}`;
    const response = await fetch(api_endpoint);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    // 日本語と英語を結合
    const statementText =
      `${data.title_ja}\n${data.statement_ja}\n\n${data.title_en}\n${data.statement_en}`.trim();

    setProblemStatement(statementText || "NULL");
    setProblemInput(data.input || "NULL");
    setProblemOutput(data.expected_output || "NULL");
    setProblemImage(soj_url + data.image);
  } catch (error) {
    console.error("Failed to get problem:", error);
    setProblemStatement("Error: Failed to get problem");
    setProblemInput("Error: Failed to get problem");
    setProblemOutput("Error: Failed to get problem");
    setProblemImage(`${soj_url}/image/STANDARD-00000001.jpg`);
  }
};
