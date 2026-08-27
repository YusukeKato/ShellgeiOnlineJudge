import React from "react";
import { render, screen } from "@testing-library/react";

import { judgeResult } from "./functions/judge_result";
import { postShellgei } from "./functions/post_shellgei";
import { updateProblem } from "./functions/update_problem";
import SojResult from "./tsx/result";

const SOJ_URL = "https://soj.example";

describe("legacy frontend API and display behavior", () => {
  // API変換と画面表示に関する従来挙動のテストを、このsuiteへまとめる。
  const fetchMock = jest.fn();

  beforeEach(() => {
    // 各テストを実時間やネットワークへ依存させないよう、timerとfetchをmockへ置き換える。
    jest.useFakeTimers();
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      writable: true,
      value: fetchMock,
    });
  });

  afterEach(() => {
    // timer、fetch mock、spyを初期状態へ戻し、後続テストへの状態漏れを防ぐ。
    jest.clearAllTimers();
    jest.useRealTimers();
    fetchMock.mockReset();
    jest.restoreAllMocks();
  });

  test("maps a successful shellgei response to the legacy tuple", async () => {
    // 投稿APIの成功レスポンスが従来の5要素配列へ変換されることを確認する。
    fetchMock.mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({
        output: "result",
        id: 42,
        date: "2026-08-27 12:34:56",
        judge: 1,
        image: "encoded-image",
      }),
    });

    await expect(postShellgei(SOJ_URL, "printf result", "STANDARD-00000001")).resolves.toEqual([
      "result",
      "42",
      "2026-08-27 12:34:56",
      "1",
      "encoded-image",
    ]);
    expect(fetchMock).toHaveBeenCalledWith(`${SOJ_URL}/api/shellgei`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        shellgei: "printf result",
        problem_id: "STANDARD-00000001",
      }),
    });
  });

  test("returns the legacy timeout tuple after 20 seconds", async () => {
    // APIが応答しない場合に20秒で従来のtimeout用配列を返すことを確認する。
    // timeout時に想定されるerror logは、このテスト中だけ出力しない。
    jest.spyOn(console, "error").mockImplementation(() => undefined);
    // resolveもrejectもしないPromiseで、応答しないfetchを再現する。
    fetchMock.mockReturnValue(new Promise(() => undefined));

    const result = postShellgei(SOJ_URL, "sleep 30", "STANDARD-00000001");
    jest.advanceTimersByTime(20_000);

    await expect(result).resolves.toEqual(["Timeout: 20.0s", "", "", "", ""]);
  });

  test("maps problem details and empty values to the displayed legacy values", async () => {
    // 問題文の連結、空値のNULL表示、画像URLの組み立てを確認する。
    fetchMock.mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({
        title_ja: "日本語タイトル",
        statement_ja: "日本語本文",
        title_en: "English title",
        statement_en: "English statement",
        input: "",
        expected_output: "",
        image: "/image/STANDARD-00000001.jpg",
      }),
    });
    const setProblemStatement = jest.fn();
    const setProblemInput = jest.fn();
    const setProblemOutput = jest.fn();
    const setProblemImage = jest.fn();

    await updateProblem(
      SOJ_URL,
      "STANDARD-00000001",
      setProblemStatement,
      setProblemInput,
      setProblemOutput,
      setProblemImage,
    );

    expect(setProblemStatement).toHaveBeenCalledWith(
      "日本語タイトル\n日本語本文\n\nEnglish title\nEnglish statement",
    );
    expect(setProblemInput).toHaveBeenCalledWith("NULL");
    expect(setProblemOutput).toHaveBeenCalledWith("NULL");
    expect(setProblemImage).toHaveBeenCalledWith(`${SOJ_URL}/image/STANDARD-00000001.jpg`);
  });

  test.each([
    ["1", "正解 / Correct !!😄!!"],
    ["2", "不正解 / Incorrect ...😭..."],
    ["3", "不正解 / Incorrect ...😭..."],
    ["4", "不正解 / Incorrect ...😭..."],
    ["", "不正解 / Incorrect ...😭..."],
  ])("maps verdict %s to its legacy label", (verdict, label) => {
    // 従来の判定番号が画面上の正解・不正解文言へ変換されることを確認する。
    expect(judgeResult(verdict)).toBe(label);
  });

  test("renders the response values without changing their text", () => {
    // 標準出力、判定、投稿ID、結果画像がDOMへそのまま描画されることを確認する。
    render(
      <SojResult
        outputResult={"line 1\nline 2"}
        judgeResult="正解 / Correct !!😄!!"
        imageResult="data:image/jpeg;base64,encoded-image"
        userShellgeiStatus="SHELLGEI ID: 42"
      />,
    );

    expect(document.querySelector("#user-output-text")?.textContent).toBe("line 1\nline 2");
    expect(screen.getByText("正解 / Correct !!😄!!")).toBeInTheDocument();
    expect(screen.getByText("SHELLGEI ID: 42")).toBeInTheDocument();
    expect(screen.getByAltText("result-image")).toHaveAttribute(
      "src",
      "data:image/jpeg;base64,encoded-image",
    );
  });
});
