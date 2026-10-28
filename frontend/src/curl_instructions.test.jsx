import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { LanguageProvider } from "./language";
import CurlInstructions from "./tsx/curl_instructions";

const defaultProps = {
  sojUrl: "https://soj.example",
  shellgei: "",
  problemId: "STANDARD-00000001",
};

function instructions(props = defaultProps) {
  // 本番の言語context内で案内を描画し、入力・問題変更も同じcomponentへ渡せるようにする。
  return (
    <LanguageProvider>
      <CurlInstructions {...props} />
    </LanguageProvider>
  );
}

function displayedCommand() {
  // ブラウザが描画したコード全文を取得し、コピー内容との一致を確認する。
  return document.querySelector("pre code").textContent;
}

beforeEach(() => {
  // 外部のClipboardへ書き込まず、毎回日本語の独立した状態から開始する。
  localStorage.clear();
  vi.stubGlobal("navigator", { clipboard: { writeText: vi.fn().mockResolvedValue() } });
});

afterEach(() => {
  // 今回だけのClipboard差し替えと選択範囲を片付ける。
  vi.unstubAllGlobals();
  localStorage.clear();
  window.getSelection()?.removeAllRanges();
});

test("copies the minimal heredoc example using the current origin when the API URL is unset", async () => {
  // 空入力でもシングルクォート入りの例をコピーでき、追加オプションなしで現在のoriginへ提出する。
  render(instructions({ ...defaultProps, sojUrl: "" }));
  const summary = screen.getByText("ターミナルから実行する（curl）");
  expect(summary.closest("details").open).toBe(false);
  fireEvent.click(summary);
  const command = displayedCommand();
  expect(command).toBe(
    `curl '${window.location.origin}/api/v3/submissions' \\
  -H 'Content-Type: application/json' \\
  --data-binary @- <<'JSON'
{"shellgei":"printf '%s\\\\n' 'test'","problem_id":"STANDARD-00000001"}
JSON
`,
  );
  await act(async () =>
    fireEvent.click(screen.getAllByRole("button", { name: "curlコマンドをコピー" })[0]),
  );
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith(command);
  expect(screen.getAllByRole("status")[0]).toHaveTextContent("コピーしました");
});

test("preserves quotes, substitutions and heredoc-like lines as JSON while updating the selected problem", async () => {
  // 引用符・改行・終端に似た入力を文字列として保持し、変更後の問題と入力だけをコピーする。
  const view = render(instructions());
  fireEvent.click(screen.getByText("ターミナルから実行する（curl）"));
  await act(async () =>
    fireEvent.click(screen.getAllByRole("button", { name: "curlコマンドをコピー" })[0]),
  );
  const shellgei = "printf '%s\\n' \"$(printf local)\"\nJSON\n`printf literal`\n";
  view.rerender(
    instructions({
      ...defaultProps,
      sojUrl: "https://soj.example/",
      shellgei,
      problemId: "IMAGE-00000001",
    }),
  );
  const command = displayedCommand();
  expect(command).toContain("curl 'https://soj.example/api/v3/submissions'");
  expect(command.split("\n").filter((line) => line === "JSON")).toHaveLength(1);
  expect(JSON.parse(command.split("\n")[3])).toEqual({ shellgei, problem_id: "IMAGE-00000001" });
  expect(screen.getAllByRole("status")[0]).toBeEmptyDOMElement();
  await act(async () =>
    fireEvent.click(screen.getAllByRole("button", { name: "curlコマンドをコピー" })[0]),
  );
  expect(navigator.clipboard.writeText).toHaveBeenLastCalledWith(command);
});

test.each(["denied", "unavailable"])(
  "selects the code for manual copying when Clipboard is %s",
  async (condition) => {
    // 権限拒否またはAPI非提供でも例を失わず、全文選択と手動コピー案内へ切り替える。
    if (condition === "denied") {
      navigator.clipboard.writeText.mockRejectedValue(new Error("Permission denied"));
    } else {
      vi.stubGlobal("navigator", {});
    }
    render(instructions());
    fireEvent.click(screen.getByText("ターミナルから実行する（curl）"));
    await act(async () =>
      fireEvent.click(screen.getAllByRole("button", { name: "curlコマンドをコピー" })[0]),
    );
    expect(screen.getAllByRole("status")[0]).toHaveTextContent("自動コピーできませんでした");
    expect(window.getSelection().toString()).toBe(displayedCommand());
    expect(document.activeElement).toBe(document.querySelector("pre"));
  },
);

test("does not label new input as copied when an earlier Clipboard request finishes late", async () => {
  // コピー中に入力が変わっても、古いPromiseの完了を現在の入力の成功表示へ流用しない。
  let finishCopy;
  navigator.clipboard.writeText.mockReturnValue(new Promise((resolve) => (finishCopy = resolve)));
  const view = render(instructions());
  fireEvent.click(screen.getByText("ターミナルから実行する（curl）"));
  fireEvent.click(screen.getAllByRole("button", { name: "curlコマンドをコピー" })[0]);
  view.rerender(instructions({ ...defaultProps, shellgei: "cat input.txt" }));
  await act(async () => finishCopy());
  expect(screen.getAllByRole("status")[0]).toBeEmptyDOMElement();
});

test("shows English guidance with the same command payload", () => {
  // 保存済みの英語設定でも操作と説明を翻訳し、送信内容は翻訳しない。
  localStorage.setItem("soj-language", "en");
  render(instructions());
  fireEvent.click(screen.getByText("Run from your terminal (curl)"));
  expect(screen.getAllByRole("button", { name: "Copy curl command" })[0]).toBeVisible();
  expect(JSON.parse(displayedCommand().split("\n")[3]).shellgei).toBe("printf '%s\\n' 'test'");
});

test.each(["ja", "en"])("copies GET examples for the selected problem in %s", async (language) => {
  // 一覧・詳細の取得例は日英で同じURLを使い、問題変更とAPI prefixを反映して提出例とは別にコピーする。
  localStorage.setItem("soj-language", language);
  const view = render(instructions());
  fireEvent.click(
    screen.getByText(
      language === "ja" ? "ターミナルから実行する（curl）" : "Run from your terminal (curl)",
    ),
  );
  const props = {
    ...defaultProps,
    sojUrl: "https://soj.example/prefix/",
    problemId: "PRACTICE-rs-01",
  };
  view.rerender(instructions(props));
  const command = document.querySelectorAll("pre code")[1].textContent;
  expect(command).toContain("'https://soj.example/prefix/api/problems'");
  expect(command).toContain("'https://soj.example/prefix/api/problems/PRACTICE-rs-01'");
  expect(command).not.toContain("--data");
  expect(command).not.toContain("/submissions");
  expect(command).not.toContain("-k ");
  expect(screen.getByText("expected_output")).toBeVisible();
  await act(async () =>
    fireEvent.click(
      screen.getAllByRole("button", {
        name: language === "ja" ? "curlコマンドをコピー" : "Copy curl command",
      })[1],
    ),
  );
  expect(navigator.clipboard.writeText).toHaveBeenLastCalledWith(command);
  expect(screen.getAllByRole("status")[0]).toBeEmptyDOMElement();
  expect(screen.getAllByRole("status")[1]).toHaveTextContent(
    language === "ja" ? "コピーしました" : "Copied",
  );
});

test("quotes API URLs and encodes the detail path without injecting shell syntax", () => {
  // 設定URLの引用符や展開文字、問題IDのpath区切りを端末のコードとして解釈させない。
  render(
    instructions({
      ...defaultProps,
      sojUrl: "https://soj.example/a'b$(echo local)",
      problemId: "x/y?z",
    }),
  );
  const command = document.querySelectorAll("pre code")[1].textContent;
  expect(command).toContain("'https://soj.example/a'\\''b$(echo local)/api/problems'");
  expect(command).toContain("/api/problems/x%2Fy%3Fz'");
});
