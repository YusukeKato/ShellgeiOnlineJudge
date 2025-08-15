export const postShellgei = async (
  soj_url: string,
  shellgei: string,
  selectedProblem: string,
): Promise<[string, string, string, string, string]> => {
  const timeoutMessage = "Timeout: 10.0s";
  const timeoutPromise = new Promise<Response>((_, reject) => {
    setTimeout(() => {
      reject(new Error(timeoutMessage));
    }, 10000);
  });

  try {
    const formData = new FormData();
    formData.append("shellgei", shellgei);
    formData.append("problem", selectedProblem);

    const fetchPromise = fetch(soj_url + "/connection.php", {
      method: "POST",
      body: formData,
    });
    const response = await Promise.race([fetchPromise, timeoutPromise]);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const res = await response.json();

    if (res.shellgei_output != null) {
      if (String(res.shellgei_output).length > 0 && String(res.shellgei_judge).length > 0) {
        return [
          String(res.shellgei_output),
          String(res.shellgei_id),
          String(res.shellgei_date),
          String(res.shellgei_judge),
          String(res.shellgei_image),
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
