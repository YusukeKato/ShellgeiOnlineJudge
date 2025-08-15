import { getProblem } from "./get_problem";

export const updateProblem = async (
  soj_url: string,
  selectedValue: string,
  setProblemStatement: (value: string) => void,
  setProblemInput: (value: string) => void,
  setProblemOutput: (value: string) => void,
  setProblemImage: (value: string) => void,
) => {
  try {
    const problem_statement_str = await getProblem(
      soj_url + "/problem_jp/" + selectedValue + ".txt",
    );
    setProblemStatement(problem_statement_str);
  } catch (error) {
    console.error("Failed to get problem:", error);
    setProblemStatement("Error: Failed to get problem");
  }
  try {
    const problem_input_str = await getProblem(soj_url + "/input/" + selectedValue + ".txt");
    setProblemInput(problem_input_str);
  } catch (error) {
    console.error("Failed to get problem:", error);
    setProblemInput("Error: Failed to get problem");
  }
  try {
    const problem_output_str = await getProblem(soj_url + "/output/" + selectedValue + ".txt");
    setProblemOutput(problem_output_str);
  } catch (error) {
    console.error("Failed to get problem:", error);
    setProblemOutput("Error: Failed to get problem");
  }
  setProblemImage(soj_url + "/image/" + selectedValue + ".jpg");
};
