import { postShellgei } from "./post_shellgei";
import { escapeShellgei } from "./escape_str";
import { judgeResult } from "./judge_result";

export const imageDataUrl = (image: string, mediaType: string): string | null => {
  // Base64画像と許可済みJPEG/GIF MIMEからdata URLを作り、不正MIMEならnullを返す。
  if (mediaType !== "image/jpeg" && mediaType !== "image/gif") {
    return null;
  }
  return `data:${mediaType};base64,${image}`;
};

export const submit = async (
  shellgei_limit: number,
  default_image: string,
  soj_url: string,
  shellgei: string,
  selectedProblem: string,
  setOutputResult: (value: string) => void,
  setJudgeResult: (value: string) => void,
  setImageResult: (value: string) => void,
  setUserShellgeiStatus: (value: string) => void,
) => {
  if (shellgei.length === 0) {
    setOutputResult("No input provided");
    setJudgeResult("No input provided");
    setImageResult(default_image);
  } else if (shellgei.length <= shellgei_limit) {
    setOutputResult("Running...");
    setJudgeResult("Running...");
    setImageResult(default_image);
    shellgei = escapeShellgei(shellgei);
    let [result, id, date, judge, image, imageMediaType] = await postShellgei(
      soj_url,
      shellgei,
      selectedProblem,
    );
    // 正常な空出力と通信errorを区別するため、必ず設定されるjudge codeを成功判定に使う。
    if (judge.length === 0) {
      const errorMessage = result || "Error: No result returned from server";
      setOutputResult(errorMessage);
      setJudgeResult(errorMessage);
      setUserShellgeiStatus(errorMessage);
      setImageResult(default_image);
    } else {
      judge = judgeResult(judge);
      setOutputResult(result);
      setJudgeResult(judge);
      setUserShellgeiStatus(
        "SHELLGEI ID: " + id + "\nDATE: " + date + "(JST)\nYOUR SHELLGEI: " + shellgei,
      );
      const imageUrl = imageDataUrl(image, imageMediaType);
      if (image.length === 0 || imageUrl === null) {
        setImageResult(default_image);
      } else {
        setImageResult(imageUrl);
      }
    }
  } else {
    setOutputResult("Exceeded character limit:" + shellgei_limit.toString());
    setJudgeResult("Exceeded character limit:" + shellgei_limit.toString());
    setUserShellgeiStatus("Exceeded character limit:" + shellgei_limit.toString());
    setImageResult(default_image);
  }
};
