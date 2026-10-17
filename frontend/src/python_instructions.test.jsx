import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { LanguageProvider } from "./language";
import PythonInstructions from "./tsx/python_instructions";

const defaultProps = { sojUrl: "", shellgei: "", problemId: "STANDARD-00000001" };

function instructions(props = defaultProps) {
  // 言語設定と現在の入力を本番と同じcontext経由で渡す。
  return (
    <LanguageProvider>
      <PythonInstructions {...props} />
    </LanguageProvider>
  );
}

function displayedScript() {
  // 表示全文を取得し、入力の保持とコピー内容を確認する。
  return document.querySelector("pre code").textContent;
}

beforeEach(() => {
  // 外部通信・実Clipboardへの書込みを行わず、日本語から開始する。
  localStorage.clear();
  vi.stubGlobal("navigator", { clipboard: { writeText: vi.fn().mockResolvedValue() } });
});

afterEach(() => {
  // 今回のClipboard差し替えと表示言語を片付ける。
  vi.unstubAllGlobals();
  localStorage.clear();
});

test("copies a standard-library Python script that parses the response JSON", async () => {
  // 追加依存なしで現在のoriginへ提出し、応答を辞書として読んで必要なfieldを表示する例を確認する。
  render(instructions());
  const summary = screen.getByText("Pythonスクリプトから実行する");
  expect(summary.closest("details").open).toBe(false);
  fireEvent.click(summary);
  const script = displayedScript();
  expect(script).toContain(`url = "${window.location.origin}/api/v3/submissions"`);
  expect(script).toContain("from urllib.request import Request, urlopen");
  expect(script).toContain("result = json.load(response)");
  expect(script).toContain('result["verdict"]');
  expect(script).toContain('repr(result["execution"]["stdout"])');
  expect(script).toContain('repr(result["execution"]["stderr"])');
  expect(screen.getByText("python3 submit.py")).toBeVisible();
  await act(async () =>
    fireEvent.click(screen.getByRole("button", { name: "Pythonスクリプトをコピー" })),
  );
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith(script);
  expect(screen.getByRole("status")).toHaveTextContent("コピーしました");
});

test("updates Python string literals for edited commands, problem selection and API URL", async () => {
  // 引用符・backslash・改行・Unicodeをdataとして保持し、古いコピー済み表示を残さない。
  const view = render(instructions());
  fireEvent.click(screen.getByText("Pythonスクリプトから実行する"));
  await act(async () =>
    fireEvent.click(screen.getByRole("button", { name: "Pythonスクリプトをコピー" })),
  );
  const shellgei = 'printf \'%s\\n\' "$(echo 日本語)"\n"""\n';
  view.rerender(
    instructions({ sojUrl: "https://soj.example/", shellgei, problemId: "IMAGE-00000001" }),
  );
  const script = displayedScript();
  expect(script).toContain('url = "https://soj.example/api/v3/submissions"');
  expect(script).toContain(`"shellgei": ${JSON.stringify(shellgei)},`);
  expect(script).toContain('"problem_id": "IMAGE-00000001",');
  expect(screen.getByRole("status")).toBeEmptyDOMElement();
  await act(async () =>
    fireEvent.click(screen.getByRole("button", { name: "Pythonスクリプトをコピー" })),
  );
  expect(navigator.clipboard.writeText).toHaveBeenLastCalledWith(script);
});

test("shows English Python instructions without translating the script", () => {
  // 保存済みの英語設定でも、同じスクリプトと実行手順を提供する。
  localStorage.setItem("soj-language", "en");
  render(instructions());
  fireEvent.click(screen.getByText("Run from a Python script"));
  expect(screen.getByRole("button", { name: "Copy Python script" })).toBeVisible();
  expect(displayedScript()).toContain("result = json.load(response)");
});
