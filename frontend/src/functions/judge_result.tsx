export const judgeResult = (judge: string): string => {
  if (judge.indexOf("1") !== -1) {
    return "正解 / Correct !!😄!!";
  } else {
    return "不正解 / Incorrect ...😭...";
  }
};
