import { postShellgei } from "./post_shellgei";
import { escapeShellgei } from "./escape_str";
import { judgeResult } from "./judge_result";

export const submit = async (
  shellgei_limit: number,
  soj_url: string,
  shellgei: string,
  selectedProblem: string,
  setOutputResult: (value: string) => void,
  setJudgeResult: (value: string) => void,
) => {
  if (shellgei.length === 0) {
    setOutputResult("No input provided");
    setJudgeResult("No input provided");
  } else if (shellgei.length <= shellgei_limit) {
    setOutputResult("Running...");
    setJudgeResult("Running...");
    shellgei = escapeShellgei(shellgei);
    let [result, judge] = await postShellgei(soj_url, shellgei, selectedProblem);
    if (!result || result.length === 0) {
      setOutputResult("Error: No result returned from server");
      setJudgeResult("Error: No result returned from server");
    } else {
      judge = judgeResult(judge);
      setOutputResult(result);
      setJudgeResult(judge);
    }
  } else {
    setOutputResult("Exceeded character limit:" + shellgei_limit.toString());
    setJudgeResult("Exceeded character limit:" + shellgei_limit.toString());
  }
};
