export const postShellgei = async (
  soj_url: string,
  shellgei: string,
  selectedProblem: string,
): Promise<[string, string]> => {
  try {
    const formData = new FormData();
    formData.append("shellgei", shellgei);
    formData.append("problemNum", selectedProblem);

    const response = await fetch(soj_url + "/connection.php", {
      method: "POST",
      body: formData,
    });

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
  } catch (error) {
    console.error("Failed to post shellgei:", error);
    throw error;
  }
};
