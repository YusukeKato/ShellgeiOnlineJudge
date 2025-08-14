export const postShellgei = async (
  soj_url: string,
  shellgei: string,
  selectedProblem: string,
): Promise<[string, string]> => {
  const timeoutMessage = "Timeout: 5000ms";
  const timeoutPromise = new Promise<Response>((_, reject) => {
    setTimeout(() => {
      reject(new Error(timeoutMessage));
    }, 5000);
  });

  try {
    const formData = new FormData();
    formData.append("shellgei", shellgei);
    formData.append("problemNum", selectedProblem);

    const fetchPromise = fetch(soj_url + "/connection.php", {
      method: "POST",
      body: formData,
    });
    const response = await Promise.race([fetchPromise, timeoutPromise]);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const res = await response.json();

    if (res.shellgei != null) {
      if (String(res.shellgei).length > 0 && String(res.shellgei_judge).length > 0) {
        return [String(res.shellgei), String(res.shellgei_judge)];
      } else {
        return ["", ""];
      }
    } else {
      return ["", ""];
    }
  } catch (error: any) {
    console.error("Failed to post shellgei:", error);
    if (error.message === timeoutMessage) {
      return [timeoutMessage, timeoutMessage];
    }
    return [`Error: ${error.message}`, `Error: ${error.message}`];
  }
};
