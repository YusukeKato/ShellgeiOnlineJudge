export const postShellgei = async (
  soj_url: string,
  shellgei: string,
  selectedProblem: string,
): Promise<[string, string, string, string, string]> => {
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

    if (res.output != null) {
      if (String(res.output).length > 0 && String(res.judge).length > 0) {
        return [
          String(res.output),
          String(res.id),
          String(res.date),
          String(res.judge),
          String(res.image),
        ];
      } else {
        return ["Error: response is empty", "", "", "", ""];
      }
    } else {
      return ["Error: response is null", "", "", "", ""];
    }
  } catch (error: any) {
    console.error("Failed to post shellgei:", error);
    if (error.message === timeoutMessage) {
      return [timeoutMessage, "", "", "", ""];
    }
    return [`Error: ${error.message}`, "", "", "", ""];
  }
};
