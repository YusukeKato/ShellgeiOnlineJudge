export const getProblem = async (file_name: string): Promise<string> => {
  try {
    const response = await fetch(file_name);
    if (!response.ok) {
      console.error("Error: Could not get problem files.");
      return "Error: Could not get problem files.";
    }
    let text = await response.text();
    text = text.replace(/</g, "&lt;");
    text = text.replace(/>/g, "&gt;");
    return text;
  } catch (error) {
    console.error("Fetch Error:", error);
    return "Error: Network request failed.";
  }
};
