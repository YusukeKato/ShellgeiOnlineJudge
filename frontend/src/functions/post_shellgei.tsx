export const postShellgei = async (
  soj_url: string,
  shellgei: string,
  selectedProblem: string,
): Promise<[string, string, string, string, string, string]> => {
  const timeoutMessage = "Timeout: 20.0s";
  // const api_endpoint = soj_url + ":8000/api/shellgei";
  const api_endpoint = soj_url + "/api/shellgei";
  const timeoutPromise = new Promise<Response>((_, reject) => {
    setTimeout(() => {
      reject(new Error(timeoutMessage));
    }, 20000);
  });

  try {
    const requestBody = {
      shellgei: shellgei,
      problem_id: selectedProblem,
    };

    const fetchPromise = fetch(api_endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestBody),
    });
    const response = await Promise.race([fetchPromise, timeoutPromise]);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const res = await response.json();

    // 画像問題は標準出力が空でも正常なため、outputの存在とjudgeの有無だけを検証する。
    if (res.output == null || res.judge == null) {
      return ["Error: response is null", "", "", "", "", ""];
    }
    if (String(res.judge).length === 0) {
      return ["Error: response is empty", "", "", "", "", ""];
    }
    return [
      String(res.output),
      String(res.id),
      String(res.date),
      String(res.judge),
      String(res.image),
      res.image_media_type == null ? "" : String(res.image_media_type),
    ];
  } catch (error: any) {
    console.error("Failed to post shellgei:", error);
    if (error.message === timeoutMessage) {
      return [timeoutMessage, "", "", "", "", ""];
    }
    return [`Error: ${error.message}`, "", "", "", "", ""];
  }
};
