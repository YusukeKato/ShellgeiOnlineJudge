import { postShellgei } from "./post_shellgei";
import { escapeShellgei } from "./escape_str";
import { judgeResult } from "./judge_result";

export const submit = async (
  shellgei_limit: number,
  default_image: string,
  soj_url: string,
  shellgei: string,
  selectedProblem: string,
  setOutputResult: (value: string) => void,
  setJudgeResult: (value: string) => void,
  setImageResult: (value: string) => void,
) => {
  if (shellgei.length === 0) {
    setOutputResult("No input provided");
    setJudgeResult("No input provided");
    setImageResult(default_image);
  } else if (shellgei.length <= shellgei_limit) {
    setOutputResult("Running...");
    setJudgeResult("Running...");
    setImageResult(soj_url + "/problem_images/GENERAL-00000001.jpg");
    shellgei = escapeShellgei(shellgei);
    let [result, judge, image] = await postShellgei(soj_url, shellgei, selectedProblem);
    if (!result || result.length === 0) {
      setOutputResult("Error: No result returned from server");
      setJudgeResult("Error: No result returned from server");
      setImageResult(default_image);
    } else {
      judge = judgeResult(judge);
      setOutputResult(result);
      setJudgeResult(judge);
      setImageResult("data:image/jpeg;base64," + image);
    }
  } else {
    setOutputResult("Exceeded character limit:" + shellgei_limit.toString());
    setJudgeResult("Exceeded character limit:" + shellgei_limit.toString());
    setImageResult(default_image);
  }
};
