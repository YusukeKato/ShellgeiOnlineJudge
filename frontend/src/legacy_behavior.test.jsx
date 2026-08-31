import React from "react";
import { render, screen } from "@testing-library/react";

import { judgeResult } from "./functions/judge_result";
import { postShellgei } from "./functions/post_shellgei";
import { imageDataUrl, submit } from "./functions/submit";
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
    // 投稿APIの成功レスポンスが画像MIMEを含む6要素配列へ変換されることを確認する。
    fetchMock.mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({
        output: "result",
        id: 42,
        date: "2026-08-27 12:34:56",
        judge: 1,
        image: "encoded-image",
        image_media_type: "image/gif",
      }),
    });

    await expect(postShellgei(SOJ_URL, "printf result", "STANDARD-00000001")).resolves.toEqual([
      "result",
      "42",
      "2026-08-27 12:34:56",
      "1",
      "encoded-image",
      "image/gif",
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

  test("preserves a successful image response with empty standard output", async () => {
    // 画像だけを生成した正常レスポンスで、空の標準出力と画像情報が失われないことを確認する。
    fetchMock.mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({
        output: "",
        id: 43,
        date: "2026-09-01 12:34:56",
        judge: 1,
        image: "encoded-image",
        image_media_type: "image/jpeg",
      }),
    });

    await expect(postShellgei(SOJ_URL, "convert image", "IMAGE-00000001")).resolves.toEqual([
      "",
      "43",
      "2026-09-01 12:34:56",
      "1",
      "encoded-image",
      "image/jpeg",
    ]);
  });

  test("displays an image and verdict when successful standard output is empty", async () => {
    // 空の標準出力をerror扱いせず、正解表示とBase64画像を画面用setterへ渡すことを確認する。
    fetchMock.mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({
        output: "",
        id: "44",
        date: "2026-09-01 12:35:00",
        judge: "1",
        image: "encoded-image",
        image_media_type: "image/jpeg",
      }),
    });
    const setOutputResult = jest.fn();
    const setJudgeResult = jest.fn();
    const setImageResult = jest.fn();
    const setUserShellgeiStatus = jest.fn();

    await submit(
      1000,
      "default-image",
      SOJ_URL,
      "convert image",
      "IMAGE-00000001",
      setOutputResult,
      setJudgeResult,
      setImageResult,
      setUserShellgeiStatus,
    );

    expect(setOutputResult).toHaveBeenLastCalledWith("");
    expect(setJudgeResult).toHaveBeenLastCalledWith("正解 / Correct !!😄!!");
    expect(setImageResult).toHaveBeenLastCalledWith("data:image/jpeg;base64,encoded-image");
    expect(setUserShellgeiStatus).toHaveBeenLastCalledWith(
      expect.stringContaining("SHELLGEI ID: 44"),
    );
  });

  test("keeps a missing image result distinct from a transport error", async () => {
    // 画像未生成による不正解も有効な応答として扱い、通信error表示に置換しないことを確認する。
    fetchMock.mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({
        output: "",
        id: "45",
        date: "2026-09-01 12:36:00",
        judge: "2",
        image: "",
        image_media_type: null,
      }),
    });
    const setOutputResult = jest.fn();
    const setJudgeResult = jest.fn();
    const setImageResult = jest.fn();
    const setUserShellgeiStatus = jest.fn();

    await submit(
      1000,
      "default-image",
      SOJ_URL,
      "true",
      "IMAGE-00000001",
      setOutputResult,
      setJudgeResult,
      setImageResult,
      setUserShellgeiStatus,
    );

    expect(setOutputResult).toHaveBeenLastCalledWith("");
    expect(setJudgeResult).toHaveBeenLastCalledWith("不正解 / Incorrect ...😭...");
    expect(setImageResult).toHaveBeenLastCalledWith("default-image");
    expect(setUserShellgeiStatus).toHaveBeenLastCalledWith(
      expect.stringContaining("SHELLGEI ID: 45"),
    );
  });

  test("shows a failed HTTP request as an error instead of a verdict", async () => {
    // HTTP失敗ではjudge codeがないため、誤って不正解へ変換せずerror内容を各表示へ渡すことを確認する。
    jest.spyOn(console, "error").mockImplementation(() => undefined);
    fetchMock.mockResolvedValue({ ok: false, status: 503 });
    const setOutputResult = jest.fn();
    const setJudgeResult = jest.fn();
    const setImageResult = jest.fn();
    const setUserShellgeiStatus = jest.fn();

    await submit(
      1000,
      "default-image",
      SOJ_URL,
      "true",
      "IMAGE-00000001",
      setOutputResult,
      setJudgeResult,
      setImageResult,
      setUserShellgeiStatus,
    );

    const errorMessage = "Error: HTTP error! status: 503";
    expect(setOutputResult).toHaveBeenLastCalledWith(errorMessage);
    expect(setJudgeResult).toHaveBeenLastCalledWith(errorMessage);
    expect(setUserShellgeiStatus).toHaveBeenLastCalledWith(errorMessage);
    expect(setImageResult).toHaveBeenLastCalledWith("default-image");
  });

  test("returns the legacy timeout tuple after 20 seconds", async () => {
    // APIが応答しない場合に20秒で従来のtimeout用配列を返すことを確認する。
    // timeout時に想定されるerror logは、このテスト中だけ出力しない。
    jest.spyOn(console, "error").mockImplementation(() => undefined);
    // resolveもrejectもしないPromiseで、応答しないfetchを再現する。
    fetchMock.mockReturnValue(new Promise(() => undefined));

    const result = postShellgei(SOJ_URL, "sleep 30", "STANDARD-00000001");
    jest.advanceTimersByTime(20_000);

    await expect(result).resolves.toEqual(["Timeout: 20.0s", "", "", "", "", ""]);
  });

  test("builds data URLs only for declared JPEG and GIF artifacts", () => {
    // backendが返すJPEG/GIF MIMEだけをdata URLへ反映し、未知MIMEを拒否する。
    expect(imageDataUrl("jpeg-data", "image/jpeg")).toBe("data:image/jpeg;base64,jpeg-data");
    expect(imageDataUrl("gif-data", "image/gif")).toBe("data:image/gif;base64,gif-data");
    expect(imageDataUrl("svg-data", "image/svg+xml")).toBeNull();
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
