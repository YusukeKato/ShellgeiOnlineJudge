import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { submitSolution } from "./api/client";
import { judgeResult } from "./functions/judge_result";
import { imageDataUrl, prepareSubmission, submissionDisplay, submit } from "./functions/submit";
import { updateProblem } from "./functions/update_problem";
import SojResult from "./tsx/result";

const SOJ_URL = "https://soj.example";

const submissionResponse = (overrides = {}) => ({
  // 正常なv3 fixtureへテスト固有のfield上書きを適用して返す。
  api_version: 3,
  submission_id: 42,
  submitted_at: "2026-09-03T12:34:56+09:00",
  verdict: "accepted",
  reason: null,
  execution: {
    status: "completed",
    stdout: "result",
    stderr: "",
    exit_code: 0,
    timed_out: false,
    truncated: false,
    duration_ms: 12,
  },
  artifact: null,
  persistence: "saved",
  ...overrides,
});

const executeSubmission = async (shellgei, problemId = "STANDARD-00000001") => {
  // テスト入力からrunning stateを作ってAPI送信し、完了後の判別可能なstateを返す。
  const prepared = prepareSubmission(1000, shellgei, problemId);
  if (prepared.kind !== "running") {
    throw new Error("test submission was not valid");
  }
  return submit(SOJ_URL, prepared, new AbortController().signal);
};

describe("typed frontend API and display behavior", () => {
  // v3 API契約の検証と、既存画面への明示的な変換をこのsuiteで確認する。
  const fetchMock = vi.fn();

  beforeEach(() => {
    // 各テストを実時間やネットワークへ依存させないよう、timerとfetchをmockへ置き換える。
    vi.useFakeTimers();
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      writable: true,
      value: fetchMock,
    });
  });

  afterEach(() => {
    // timer、fetch mock、spyを初期状態へ戻し、後続テストへの状態漏れを防ぐ。
    vi.clearAllTimers();
    vi.useRealTimers();
    fetchMock.mockReset();
    vi.restoreAllMocks();
  });

  test("returns a validated typed submission response", async () => {
    // 正常なv3 fixtureがtupleへ変換されず、分離出力や型付きverdictを保ったDTOで返ることを確認する。
    fetchMock.mockResolvedValue({
      ok: true,
      headers: new Headers({ "X-Request-ID": "a".repeat(32) }),
      json: vi.fn().mockResolvedValue(submissionResponse()),
    });

    await expect(
      submitSolution(SOJ_URL, {
        shellgei: "printf result",
        problem_id: "STANDARD-00000001",
      }),
    ).resolves.toEqual(submissionResponse());
    expect(fetchMock).toHaveBeenCalledWith(
      `${SOJ_URL}/api/v3/submissions`,
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shellgei: "printf result",
          problem_id: "STANDARD-00000001",
        }),
        signal: expect.any(AbortSignal),
      }),
    );
  });

  test("preserves a successful image response with empty standard output", async () => {
    // 画像だけを生成したv3応答で、空の標準出力とtyped artifactが画面表示まで失われないことを確認する。
    fetchMock.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(
        submissionResponse({
          submission_id: 43,
          execution: {
            status: "completed",
            stdout: "",
            stderr: "",
            exit_code: 0,
            timed_out: false,
            truncated: false,
            duration_ms: 13,
          },
          artifact: { data: "encoded-image", media_type: "image/jpeg" },
        }),
      ),
    });

    const state = await executeSubmission("convert image", "IMAGE-00000001");
    const display = submissionDisplay(state, "default-image");

    expect(display.output).toBe("");
    expect(display.image).toBe("data:image/jpeg;base64,encoded-image");
  });

  test("displays an image and verdict when successful standard output is empty", async () => {
    // 空の標準出力をerror扱いせず、正解表示とBase64画像を画面用setterへ渡すことを確認する。
    fetchMock.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(
        submissionResponse({
          submission_id: 44,
          execution: {
            status: "completed",
            stdout: "",
            stderr: "",
            exit_code: 0,
            timed_out: false,
            truncated: false,
            duration_ms: 14,
          },
          artifact: { data: "encoded-image", media_type: "image/jpeg" },
        }),
      ),
    });
    const state = await executeSubmission("convert image", "IMAGE-00000001");
    const display = submissionDisplay(state, "default-image");

    expect(display.output).toBe("");
    expect(display.verdict).toBe("正解 / Correct !!😄!!");
    expect(display.image).toBe("data:image/jpeg;base64,encoded-image");
    expect(display.commandStatus).toContain("SHELLGEI ID: 44");
  });

  test("keeps a missing image result distinct from a transport error", async () => {
    // 画像未生成による不正解も有効な応答として扱い、通信error表示に置換しないことを確認する。
    fetchMock.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(
        submissionResponse({
          submission_id: 45,
          verdict: "wrong_image",
          reason: "artifact_missing",
          execution: {
            status: "completed",
            stdout: "",
            stderr: "",
            exit_code: 0,
            timed_out: false,
            truncated: false,
            duration_ms: 15,
          },
        }),
      ),
    });
    const state = await executeSubmission("true", "IMAGE-00000001");
    const display = submissionDisplay(state, "default-image");

    expect(display.output).toBe("");
    expect(display.verdict).toBe("不正解 / Incorrect ...😭...");
    expect(display.image).toBe("default-image");
    expect(display.commandStatus).toContain("SHELLGEI ID: 45");
  });

  test("shows a failed HTTP request as an error instead of a verdict", async () => {
    // v3 HTTP失敗ではverdictがないため、誤って不正解へ変換せずerror内容を各表示へ渡すことを確認する。
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    fetchMock.mockResolvedValue({
      ok: false,
      status: 503,
      headers: new Headers({ "X-Request-ID": "b".repeat(32) }),
      json: vi.fn().mockResolvedValue({
        api_version: 3,
        code: "runner_unavailable",
        message: "Runner is unavailable",
      }),
    });
    const state = await executeSubmission("true", "IMAGE-00000001");
    const display = submissionDisplay(state, "default-image");
    const errorMessage = "Error: HTTP error! status: 503";
    expect(display.output).toBe(errorMessage);
    expect(display.verdict).toBe(errorMessage);
    expect(display.commandStatus).toBe(errorMessage);
    expect(display.image).toBe("default-image");
  });

  test("preserves a typed API error and server request ID", async () => {
    // v3 error fixtureのcode・messageと相関用request IDを、HTTP status付きclient errorへ保持する。
    fetchMock.mockResolvedValue({
      ok: false,
      status: 429,
      headers: new Headers({ "X-Request-ID": "c".repeat(32) }),
      json: vi.fn().mockResolvedValue({
        api_version: 3,
        code: "runner_busy",
        message: "Runner capacity is temporarily exhausted",
      }),
    });

    await expect(
      submitSolution(SOJ_URL, { shellgei: "true", problem_id: "STANDARD-00000001" }),
    ).rejects.toMatchObject({
      kind: "http",
      status: 429,
      requestId: "c".repeat(32),
      response: {
        api_version: 3,
        code: "runner_busy",
        message: "Runner capacity is temporarily exhausted",
      },
    });
  });

  test("returns a typed timeout error after 20 seconds", async () => {
    // APIが応答しない場合に20秒でtimeout種別のApiClientErrorを返すことを確認する。
    // timeout時に想定されるerror logは、このテスト中だけ出力しない。
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    // resolveもrejectもしないPromiseで、応答しないfetchを再現する。
    let fetchSignal;
    fetchMock.mockImplementation((_url, options) => {
      // API clientがfetchへ渡したsignalを保持し、timeout後の実abortを確認できるようにする。
      fetchSignal = options.signal;
      return new Promise(() => undefined);
    });

    const result = submitSolution(SOJ_URL, {
      shellgei: "sleep 30",
      problem_id: "STANDARD-00000001",
    });
    vi.advanceTimersByTime(20_000);

    await expect(result).rejects.toMatchObject({
      name: "ApiClientError",
      kind: "timeout",
      message: "Timeout: 20.0s",
    });
    expect(fetchSignal.aborted).toBe(true);
  });

  test("maps a submission timeout to the visible timeout state", async () => {
    // 20秒応答しない提出をfailed stateへ変換し、結果・判定・command欄へtimeoutを表示する。
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    fetchMock.mockReturnValue(new Promise(() => undefined));
    const prepared = prepareSubmission(1000, "sleep 30", "STANDARD-00000001");
    if (prepared.kind !== "running") {
      throw new Error("test submission was not valid");
    }
    const result = submit(SOJ_URL, prepared, new AbortController().signal);

    vi.advanceTimersByTime(20_000);

    const state = await result;
    expect(state).toEqual({ kind: "failed", message: "Timeout: 20.0s" });
    expect(submissionDisplay(state, "default-image")).toEqual({
      output: "Timeout: 20.0s",
      verdict: "Timeout: 20.0s",
      image: "default-image",
      commandStatus: "Timeout: 20.0s",
    });
  });

  test("aborts fetch when the caller cancels a request", async () => {
    // 呼出側AbortControllerの中断がfetch signalへ伝播し、timeoutとは異なるaborted errorになることを確認する。
    let fetchSignal;
    fetchMock.mockImplementation((_url, options) => {
      fetchSignal = options.signal;
      return new Promise(() => undefined);
    });
    const controller = new AbortController();
    const result = submitSolution(
      SOJ_URL,
      { shellgei: "sleep 30", problem_id: "STANDARD-00000001" },
      { signal: controller.signal },
    );

    controller.abort();

    await expect(result).rejects.toMatchObject({ kind: "aborted", message: "Request cancelled" });
    expect(fetchSignal.aborted).toBe(true);
  });

  test("rejects an unknown verdict before it reaches display mapping", async () => {
    // backend契約にないverdictを含む成功responseを受理せず、契約違反errorへ変換することを確認する。
    fetchMock.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(submissionResponse({ verdict: "future_verdict" })),
    });

    await expect(
      submitSolution(SOJ_URL, { shellgei: "true", problem_id: "STANDARD-00000001" }),
    ).rejects.toMatchObject({ kind: "invalid_response" });
  });

  test("rejects an undeclared artifact MIME before building a data URL", async () => {
    // JPEG/GIF以外のartifact MIMEを含むresponseを契約違反として拒否し、DOMへdata URLを渡さない。
    fetchMock.mockResolvedValue({
      ok: true,
      json: vi
        .fn()
        .mockResolvedValue(
          submissionResponse({ artifact: { data: "svg-data", media_type: "image/svg+xml" } }),
        ),
    });

    await expect(
      submitSolution(SOJ_URL, { shellgei: "true", problem_id: "IMAGE-00000001" }),
    ).rejects.toMatchObject({ kind: "invalid_response" });
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
      json: vi.fn().mockResolvedValue({
        title_ja: "日本語タイトル",
        statement_ja: "日本語本文",
        title_en: "English title",
        statement_en: "English statement",
        input: "",
        expected_output: "",
        image: "/image/STANDARD-00000001.jpg",
      }),
    });
    const problem = await updateProblem(SOJ_URL, "STANDARD-00000001", new AbortController().signal);

    expect(problem.statement).toBe(
      "日本語タイトル\n日本語本文\n\nEnglish title\nEnglish statement",
    );
    expect(problem.input).toBe("NULL");
    expect(problem.output).toBe("NULL");
    expect(problem.image).toBe(`${SOJ_URL}/image/STANDARD-00000001.jpg`);
  });

  test.each([
    ["accepted", "正解 / Correct !!😄!!"],
    ["wrong_answer", "不正解 / Incorrect ...😭..."],
    ["wrong_image", "不正解 / Incorrect ...😭..."],
    ["wrong_text_and_image", "不正解 / Incorrect ...😭..."],
    ["execution_failure", "実行失敗: コマンドの実行に失敗しました / Command execution failed"],
    ["judge_error", "判定エラー: 判定処理でエラーが発生しました / Judging failed"],
  ])("maps typed verdict %s to its display label", (verdict, label) => {
    // reasonがない契約内の値でも、正解・不正解・実行失敗・判定エラーを区別する。
    expect(judgeResult(verdict, null)).toBe(label);
  });

  test.each([
    [
      "timed_out",
      "execution_failure",
      { status: "timed_out", exit_code: null, timed_out: true },
      "実行失敗: 実行がタイムアウトしました / Execution timed out",
    ],
    [
      "output_truncated",
      "execution_failure",
      { status: "output_limit", exit_code: null, truncated: true },
      "実行失敗: 出力上限を超えました / Output limit exceeded",
    ],
    [
      "execution_error",
      "execution_failure",
      { status: "error", exit_code: null },
      "実行失敗: コマンドの実行に失敗しました / Command execution failed",
    ],
    [
      "non_zero_exit",
      "execution_failure",
      { exit_code: 1 },
      "実行失敗: コマンドが非0の終了コードで終了しました / Command exited with a non-zero status",
    ],
    [
      "stderr_not_empty",
      "execution_failure",
      { stderr: "diagnostic" },
      "実行失敗: 許可されていない標準エラー出力がありました / Standard error output is not allowed",
    ],
    [
      "invalid_problem_id",
      "judge_error",
      {},
      "判定エラー: 判定処理でエラーが発生しました / Judging failed",
    ],
    [
      "problem_not_found",
      "judge_error",
      {},
      "判定エラー: 判定処理でエラーが発生しました / Judging failed",
    ],
  ])(
    "renders the API failure reason %s distinctly from wrong answers",
    async (reason, verdict, execution, label) => {
      // backendが構築するstatus・reasonの組合せをAPI clientからDOMまで通し、不正解と区別する。
      // 判定欄は固定文言だけを表示し、出力や内部識別用のreasonをそのまま表示しない。
      fetchMock.mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue(
          submissionResponse({
            verdict,
            reason,
            execution: { ...submissionResponse().execution, ...execution },
          }),
        ),
      });

      const state = await executeSubmission("test command");
      expect(state.kind).toBe("succeeded");
      render(<SojResult submissionState={state} defaultImage="default-image" />);

      expect(document.querySelector("#result-text")?.textContent).toBe(label);
      expect(screen.queryByText("不正解 / Incorrect ...😭...")).not.toBeInTheDocument();
    },
  );

  test("preserves accepted verdicts when the problem permits a non-zero exit", async () => {
    // exit_codeをignoreする問題の正解を、frontendが終了codeだけで実行失敗へ再判定しない。
    fetchMock.mockResolvedValue({
      ok: true,
      json: vi
        .fn()
        .mockResolvedValue(
          submissionResponse({ execution: { ...submissionResponse().execution, exit_code: 1 } }),
        ),
    });

    const state = await executeSubmission("test command");
    expect(submissionDisplay(state, "default-image").verdict).toBe("正解 / Correct !!😄!!");
  });

  test("rejects an unknown reason before it reaches display mapping", async () => {
    // API契約外の自由文reasonを表示層へ渡さず、既存clientが契約違反として拒否する。
    fetchMock.mockResolvedValue({
      ok: true,
      json: vi
        .fn()
        .mockResolvedValue(
          submissionResponse({ verdict: "judge_error", reason: "internal detail /host/private" }),
        ),
    });

    await expect(
      submitSolution(SOJ_URL, { shellgei: "true", problem_id: "STANDARD-00000001" }),
    ).rejects.toMatchObject({ kind: "invalid_response" });
  });

  test("renders the response values without changing their text", () => {
    // 標準出力、判定、投稿ID、結果画像がDOMへそのまま描画されることを確認する。
    render(
      <SojResult
        submissionState={{
          kind: "succeeded",
          shellgei: "printf result",
          problemId: "STANDARD-00000001",
          response: submissionResponse({
            execution: {
              status: "completed",
              stdout: "line 1\nline 2",
              stderr: "",
              exit_code: 0,
              timed_out: false,
              truncated: false,
              duration_ms: 1,
            },
            artifact: { data: "encoded-image", media_type: "image/jpeg" },
          }),
        }}
        defaultImage="default-image"
      />,
    );

    expect(document.querySelector("#user-output-text")?.textContent).toBe("line 1\nline 2");
    expect(screen.getByText("正解 / Correct !!😄!!")).toBeInTheDocument();
    expect(document.querySelector("#shellgei-text")?.textContent).toContain("SHELLGEI ID: 42");
    expect(screen.getByAltText("result-image")).toHaveAttribute(
      "src",
      "data:image/jpeg;base64,encoded-image",
    );
  });
});
