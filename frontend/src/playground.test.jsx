import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { LanguageProvider, useLanguage } from "./language";
import Playground from "./tsx/playground";
import { BrowserRouter } from "react-router-dom";

const SOJ_URL = "https://soj.example";
const DEFAULT_PROBLEM_ID = "STANDARD-00000001";
const SECOND_PROBLEM_ID = "STANDARD-00000002";
const IMAGE_PROBLEM_ID = "IMAGE-00000001";

const LanguageControls = () => {
  // 実際のcontext操作で言語だけを切り替え、通信や提出stateが維持されるか検証可能にする。
  const { setLanguage } = useLanguage();
  return (
    <>
      <button onClick={() => setLanguage("en")}>Test English</button>
      <button onClick={() => setLanguage("ja")}>Test Japanese</button>
    </>
  );
};

const renderPlayground = () => {
  // 本番と同じproviderを通して問題画面を描画し、表示言語と入力・通信の関係を確認する。
  return render(
    <BrowserRouter>
      <LanguageProvider>
        <LanguageControls />
        <Playground soj_url={SOJ_URL} />
      </LanguageProvider>
    </BrowserRouter>,
  );
};

const runButton = () => {
  // 待機中と実行中のどちらでも、文言だけが変わった同じ提出操作を利用する。
  return screen.getByRole("button", {
    name: /実行する|実行中…|Run command|Running…/,
  });
};

const selectProblem = async (title) => {
  // 初期状態で閉じている問題選択を利用者と同じ操作で開き、選択可能なbuttonを押す。
  const summary = screen.getByText(/問題を選ぶ|Choose problem/).closest("summary");
  if (!summary.parentElement.open) {
    fireEvent.click(summary);
  }
  fireEvent.click(await screen.findByRole("button", { name: new RegExp(title) }));
};

const problemListResponse = () => ({
  // 通常問題2問・練習問題・画像問題を返し、選択raceとカテゴリ別の画像表示を確認できるようにする。
  ok: true,
  json: async () => [
    {
      id: DEFAULT_PROBLEM_ID,
      category: "STANDARD",
      title_ja: "標準問題1",
      title_en: "Standard problem 1",
    },
    {
      id: SECOND_PROBLEM_ID,
      category: "STANDARD",
      title_ja: "標準問題2",
      title_en: "Standard problem 2",
    },
    {
      id: "PRACTICE-00000001",
      category: "PRACTICE",
      title_ja: "練習問題1",
      title_en: "Practice problem 1",
    },
    {
      id: IMAGE_PROBLEM_ID,
      category: "IMAGE",
      title_ja: "画像問題1",
      title_en: "Image problem 1",
    },
  ],
});

const problemDetailResponse = (problemId) => {
  // 入力IDに対応する問題番号を本文へ含め、どの問題詳細が画面へ反映されたか判別可能にする。
  const number = problemId === DEFAULT_PROBLEM_ID ? "1" : "2";
  return {
    ok: true,
    json: async () => ({
      title_ja: `標準問題${number}`,
      statement_ja: `日本語の問題文${number}`,
      title_en: `Standard problem ${number}`,
      statement_en: `English statement ${number}`,
      input: `入力例${number}`,
      expected_output: `出力例${number}`,
      image: `/image/${problemId}.jpg`,
    }),
  };
};

const submissionResponse = (stdout, submissionId) => ({
  // 指定出力とIDを持つ正常なv3提出responseを返し、応答順のテストで結果を識別する。
  ok: true,
  json: async () => ({
    api_version: 3,
    submission_id: submissionId,
    submitted_at: "2026-09-01T00:00:00+09:00",
    verdict: "accepted",
    reason: null,
    execution: {
      status: "completed",
      stdout,
      stderr: "",
      exit_code: 0,
      timed_out: false,
      truncated: false,
      duration_ms: 1,
    },
    artifact: null,
    persistence: "saved",
  }),
});

const deferredResponse = () => {
  // テスト側で任意の順序に完了させられるresponse Promiseとresolve関数を返す。
  let resolve;
  const promise = new Promise((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
};

const defaultFetchResponse = async (url, options) => {
  // 通常の問題一覧・詳細・提出URLへ、外部通信を行わず成功fixtureを返す。
  if (url === `${SOJ_URL}/api/problems`) {
    return problemListResponse();
  }
  if (url.startsWith(`${SOJ_URL}/api/problems/`)) {
    return problemDetailResponse(url.split("/").at(-1));
  }
  if (url === `${SOJ_URL}/api/v3/submissions` && options?.method === "POST") {
    return submissionResponse("ok", 1);
  }
  throw new Error(`Unexpected fetch: ${url}`);
};

describe("playground default problem", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    // 問題一覧・問題詳細・投稿APIをURL別に応答させ、初期表示と送信内容を外部通信なしで確認する。
    window.history.replaceState({}, "", "/");
    fetchMock.mockImplementation(defaultFetchResponse);
    localStorage.clear();
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      writable: true,
      value: fetchMock,
    });
  });

  afterEach(() => {
    // 呼び出し履歴とmock実装を破棄し、後続テストへ通信状態を持ち越さない。
    fetchMock.mockReset();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  test.each([SECOND_PROBLEM_ID, IMAGE_PROBLEM_ID, "PRACTICE-00000001"])(
    "opens the problem in a shared URL: %s",
    async (id) => {
      // 直接開いたURLから詳細を取得し、初期問題や提出を余分に要求しない。
      window.history.replaceState({}, "", `/?problem=${id}`);
      renderPlayground();
      await screen.findByText(/日本語の問題文2/);
      expect(document.querySelector("#selected-text")).toHaveTextContent(id);
      expect(fetchMock.mock.calls.map(([url]) => url)).not.toContain(
        `${SOJ_URL}/api/problems/${DEFAULT_PROBLEM_ID}`,
      );
      expect(fetchMock.mock.calls.some(([, options]) => options?.method === "POST")).toBe(false);
      fireEvent.click(screen.getByText(/問題を選ぶ/).closest("summary"));
      const category = id.startsWith("IMAGE")
        ? "画像"
        : id.startsWith("PRACTICE")
          ? "練習"
          : "通常";
      expect(screen.getByRole("button", { name: category, exact: true })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
    },
  );

  test.each(["", "../../about", "<script>", "A".repeat(65)])(
    "replaces an invalid problem URL and explains the fallback: %s",
    async (id) => {
      // 不正IDはAPIへ渡さず、他のqueryとfragmentを保持して標準問題へ置換する。
      window.history.replaceState(
        {},
        "",
        `/?keep=yes&problem=${encodeURIComponent(id)}#main-content`,
      );
      renderPlayground();
      await screen.findByText(/日本語の問題文1/);
      expect(screen.getByRole("alert")).toHaveTextContent(/Invalid or unknown problem/);
      expect(new URLSearchParams(window.location.search).get("problem")).toBe(DEFAULT_PROBLEM_ID);
      expect(new URLSearchParams(window.location.search).get("keep")).toBe("yes");
      expect(window.location.hash).toBe("#main-content");
      expect(fetchMock.mock.calls.filter(([url]) => url.includes("/api/problems/"))).toHaveLength(
        1,
      );
    },
  );

  test.each([404, 500])(
    "handles problem HTTP %s without hiding server failures",
    async (status) => {
      // 未登録IDの404だけ標準問題へ戻し、サーバ障害を問題IDの誤りと扱わない。
      window.history.replaceState({}, "", "/?problem=STANDARD-99999999");
      fetchMock.mockImplementation((url, options) =>
        url.endsWith("/STANDARD-99999999")
          ? Promise.resolve({ ok: false, status, json: async () => ({}) })
          : defaultFetchResponse(url, options),
      );
      renderPlayground();
      if (status === 404) {
        await screen.findByText(/日本語の問題文1/);
        expect(screen.getByRole("alert")).toHaveTextContent(/Invalid or unknown problem/);
        expect(new URLSearchParams(window.location.search).get("problem")).toBe(DEFAULT_PROBLEM_ID);
      } else {
        await screen.findByText("Error: Failed to get problem");
        expect(window.location.search).toBe("?problem=STANDARD-99999999");
        expect(screen.queryByText(/Invalid or unknown problem/)).not.toBeInTheDocument();
      }
    },
  );

  test("updates shared URLs and restores selection with back and forward", async () => {
    // 履歴移動で選択・カテゴリを復元しても入力と提出結果は保持する。
    window.history.replaceState({}, "", `/?problem=${DEFAULT_PROBLEM_ID}`);
    renderPlayground();
    await screen.findByText(/日本語の問題文1/);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "printf keep" } });
    await selectProblem("標準問題2");
    await screen.findByText(/日本語の問題文2/);
    expect(window.location.search).toBe(`?problem=${SECOND_PROBLEM_ID}`);
    fireEvent.click(runButton());
    await waitFor(() =>
      expect(document.querySelector("#user-output-text")).toHaveTextContent("ok"),
    );
    act(() => window.history.back());
    await screen.findByText(/日本語の問題文1/);
    expect(screen.getByRole("textbox")).toHaveValue("printf keep");
    expect(document.querySelector("#user-output-text")).toHaveTextContent("ok");
    act(() => window.history.forward());
    await screen.findByText(/日本語の問題文2/);
    expect(document.querySelector("#selected-text")).toHaveTextContent(SECOND_PROBLEM_ID);
  });

  test("rejects duplicate problem parameters without adding a history entry", async () => {
    // 複数IDの曖昧な指定は先勝ちにせず、履歴を増やさず正常なURLへ戻す。
    window.history.replaceState(
      {},
      "",
      `/?problem=${DEFAULT_PROBLEM_ID}&problem=${SECOND_PROBLEM_ID}`,
    );
    const entries = window.history.length;
    renderPlayground();
    await screen.findByText(/日本語の問題文1/);
    expect(new URLSearchParams(window.location.search).getAll("problem")).toEqual([
      DEFAULT_PROBLEM_ID,
    ]);
    expect(window.history.length).toBe(entries);
    await selectProblem("標準問題2");
    await screen.findByText(/日本語の問題文2/);
    expect(screen.queryByText(/Invalid or unknown problem/)).not.toBeInTheDocument();
  });

  test("ignores a late 404 after choosing another problem", async () => {
    // abortを無視する旧404が後から届いても、選択済み問題やURLを初期値へ戻さない。
    const pending = deferredResponse();
    window.history.replaceState({}, "", "/?problem=STANDARD-99999999");
    fetchMock.mockImplementation((url, options) =>
      url.endsWith("/STANDARD-99999999") ? pending.promise : defaultFetchResponse(url, options),
    );
    renderPlayground();
    await selectProblem("標準問題2");
    await screen.findByText(/日本語の問題文2/);
    await act(async () => pending.resolve({ ok: false, status: 404, json: async () => ({}) }));
    expect(window.location.search).toBe(`?problem=${SECOND_PROBLEM_ID}`);
    expect(screen.queryByText(/Invalid or unknown problem/)).not.toBeInTheDocument();
  });

  test("restores image category on history navigation during submission", async () => {
    // 履歴移動でもカテゴリと問題が一致し、実行中の提出は送信時の問題に紐づいたまま続く。
    const pending = deferredResponse();
    let signal;
    fetchMock.mockImplementation((url, options) => {
      if (options?.method === "POST") {
        signal = options.signal;
        return pending.promise;
      }
      return defaultFetchResponse(url, options);
    });
    window.history.replaceState({}, "", `/?problem=${IMAGE_PROBLEM_ID}`);
    renderPlayground();
    await screen.findByText(/日本語の問題文2/);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "printf running" } });
    fireEvent.click(runButton());
    fireEvent.click(screen.getByText(/問題を選ぶ/).closest("summary"));
    fireEvent.click(screen.getByRole("button", { name: "通常", exact: true }));
    await selectProblem("標準問題1");
    await screen.findByText(/日本語の問題文1/);
    act(() => window.history.back());
    await screen.findByText(/日本語の問題文2/);
    fireEvent.click(screen.getByText(/問題を選ぶ/).closest("summary"));
    expect(screen.getByRole("button", { name: "画像", exact: true })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(signal.aborted).toBe(false);
    expect(fetchMock.mock.calls.filter(([, options]) => options?.method === "POST")).toHaveLength(
      1,
    );
    await act(async () => pending.resolve(submissionResponse("image result", 2)));
    expect(document.querySelector("#user-output-text")).toHaveTextContent("image result");
  });

  test("selects and loads standard problem 1 on the initial render", async () => {
    // 利用者が操作しなくても標準問題1番が選択され、その問題詳細と選択行が表示されることを確認する。
    renderPlayground();

    expect(document.querySelector("#selected-text")?.textContent).toBe(DEFAULT_PROBLEM_ID);
    expect(await screen.findByText(/日本語の問題文1/)).toBeInTheDocument();
    const summary = screen.getByText(/問題を選ぶ/).closest("summary");
    expect(summary.parentElement.open).toBe(false);
    fireEvent.click(summary);
    expect(screen.getByRole("button", { name: /標準問題1/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
  });

  test("submits standard problem 1 without an explicit problem click", async () => {
    // 初期状態のままコマンドを実行した場合も、有効な標準問題1番のIDが投稿APIへ送られることを確認する。
    renderPlayground();

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "printf ok" },
    });
    fireEvent.click(runButton());

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `${SOJ_URL}/api/v3/submissions`,
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            shellgei: "printf ok",
            problem_id: DEFAULT_PROBLEM_ID,
          }),
          signal: expect.any(AbortSignal),
        }),
      );
    });
  });

  test("does not send the same in-flight submission twice", async () => {
    // 同じcommandと問題で実行操作を連続しても、進行中のHTTP提出が1回だけであることを確認する。
    const pendingSubmission = deferredResponse();
    fetchMock.mockImplementation((url, options) => {
      if (url === `${SOJ_URL}/api/v3/submissions`) {
        return pendingSubmission.promise;
      }
      return defaultFetchResponse(url, options);
    });
    renderPlayground();
    await screen.findByText(/日本語の問題文1/);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "sleep 1" },
    });

    fireEvent.click(runButton());
    fireEvent.click(runButton());

    await waitFor(() => {
      const submissions = fetchMock.mock.calls.filter(
        ([url]) => url === `${SOJ_URL}/api/v3/submissions`,
      );
      expect(submissions).toHaveLength(1);
    });
  });

  test("keeps the latest submission when responses complete out of order", async () => {
    // 異なる2回目の提出で1回目をabortし、旧fetchが後から成功しても最新結果を維持することを確認する。
    const first = deferredResponse();
    const second = deferredResponse();
    const submittedSignals = [];
    fetchMock.mockImplementation((url, options) => {
      if (url === `${SOJ_URL}/api/v3/submissions`) {
        submittedSignals.push(options.signal);
        return submittedSignals.length === 1 ? first.promise : second.promise;
      }
      return defaultFetchResponse(url, options);
    });
    renderPlayground();
    await screen.findByText(/日本語の問題文1/);
    const input = screen.getByRole("textbox");

    fireEvent.change(input, { target: { value: "printf first" } });
    fireEvent.click(runButton());
    fireEvent.change(input, { target: { value: "printf second" } });
    fireEvent.click(runButton());

    expect(submittedSignals[0].aborted).toBe(true);
    await act(async () => {
      second.resolve(submissionResponse("second", 2));
    });
    await waitFor(() => {
      expect(document.querySelector("#user-output-text")?.textContent).toBe("second");
    });

    await act(async () => {
      first.resolve(submissionResponse("first", 1));
    });
    expect(document.querySelector("#user-output-text")?.textContent).toBe("second");
    expect(document.querySelector("#shellgei-text")?.textContent).toContain("printf second");
  });

  test("keeps the latest problem when detail responses complete out of order", async () => {
    // 初期問題の遅いresponseが選択後に届いても、選択した2番の問題詳細を上書きしないことを確認する。
    const first = deferredResponse();
    const second = deferredResponse();
    fetchMock.mockImplementation((url, options) => {
      if (url === `${SOJ_URL}/api/problems/${DEFAULT_PROBLEM_ID}`) {
        return first.promise;
      }
      if (url === `${SOJ_URL}/api/problems/${SECOND_PROBLEM_ID}`) {
        return second.promise;
      }
      return defaultFetchResponse(url, options);
    });
    renderPlayground();
    await selectProblem("標準問題2");

    await act(async () => {
      second.resolve(problemDetailResponse(SECOND_PROBLEM_ID));
    });
    expect(await screen.findByText(/日本語の問題文2/)).toBeInTheDocument();

    await act(async () => {
      first.resolve(problemDetailResponse(DEFAULT_PROBLEM_ID));
    });
    expect(screen.getByText(/日本語の問題文2/)).toBeInTheDocument();
    expect(screen.queryByText(/日本語の問題文1/)).not.toBeInTheDocument();
  });

  test("changes language during a pending problem request without resetting the command", async () => {
    // 問題取得中に言語を変えても同じ通信を維持し、完了時は最新言語で選択した問題を表示する。
    const pendingDetail = deferredResponse();
    let detailSignal;
    fetchMock.mockImplementation((url, options) => {
      if (url === `${SOJ_URL}/api/problems/${SECOND_PROBLEM_ID}`) {
        detailSignal = options.signal;
        return pendingDetail.promise;
      }
      return defaultFetchResponse(url, options);
    });
    renderPlayground();
    await screen.findByText(/日本語の問題文1/);
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "printf '入力を保持'" } });
    await selectProblem("標準問題2");
    const callsBeforeSwitch = fetchMock.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: "Test English" }));

    expect(input).toHaveValue("printf '入力を保持'");
    expect(document.querySelector("#selected-text")?.textContent).toBe(SECOND_PROBLEM_ID);
    expect(detailSignal.aborted).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(callsBeforeSwitch);
    await act(async () => {
      pendingDetail.resolve(problemDetailResponse(SECOND_PROBLEM_ID));
    });
    expect(await screen.findByText("English statement 2")).toBeInTheDocument();
    expect(screen.queryByText("日本語の問題文2")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(callsBeforeSwitch);
  });

  test("changes language during a pending submission without aborting or resending it", async () => {
    // 提出中の言語変更は入力・提出先・通信を維持し、完了した判定だけを選択言語で表示する。
    const pendingSubmission = deferredResponse();
    let submissionSignal;
    fetchMock.mockImplementation((url, options) => {
      if (url === `${SOJ_URL}/api/v3/submissions`) {
        submissionSignal = options.signal;
        return pendingSubmission.promise;
      }
      return defaultFetchResponse(url, options);
    });
    renderPlayground();
    await screen.findByText(/日本語の問題文1/);
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "printf 日本語" } });
    fireEvent.click(runButton());
    const callsBeforeSwitch = fetchMock.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: "Test English" }));

    expect(screen.getByRole("button", { name: /Running…/ })).toBeEnabled();
    expect(input).toHaveValue("printf 日本語");
    expect(document.querySelector("#selected-text")?.textContent).toBe(DEFAULT_PROBLEM_ID);
    expect(submissionSignal.aborted).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(callsBeforeSwitch);
    await act(async () => {
      pendingSubmission.resolve(submissionResponse("日本語の出力\n", 7));
    });
    expect(document.querySelector("#result-text")?.textContent).toBe("Accepted");
    expect(document.querySelector("#user-output-text")?.textContent).toBe("日本語の出力\n");
    expect(document.querySelector("#shellgei-text")?.textContent).toContain("printf 日本語");
    expect(fetchMock).toHaveBeenCalledTimes(callsBeforeSwitch);
  });

  test("keeps completed results and input while changing the display language", async () => {
    // 取得済みの問題・結果を再取得せずに翻訳し、入力や実行出力の空白・改行を変更しない。
    renderPlayground();
    await screen.findByText(/日本語の問題文1/);
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "printf ok" } });
    fireEvent.click(runButton());
    await waitFor(() => {
      expect(document.querySelector("#result-text")?.textContent).toBe("正解");
    });
    fireEvent.change(input, { target: { value: "printf '次の入力'" } });
    const callsBeforeSwitch = fetchMock.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: "Test English" }));

    expect(screen.getByText("English statement 1")).toBeInTheDocument();
    expect(document.querySelector("#result-text")?.textContent).toBe("Accepted");
    expect(document.querySelector("#user-output-text")?.textContent).toBe("ok");
    expect(document.querySelector("#shellgei-text")?.textContent).toContain("printf ok");
    expect(input).toHaveValue("printf '次の入力'");
    expect(document.querySelector("#selected-text")?.textContent).toBe(DEFAULT_PROBLEM_ID);
    fireEvent.click(screen.getByRole("button", { name: "Test Japanese" }));
    expect(screen.getByText("日本語の問題文1")).toBeInTheDocument();
    expect(document.querySelector("#result-text")?.textContent).toBe("正解");
    expect(fetchMock).toHaveBeenCalledTimes(callsBeforeSwitch);
  });

  test("keeps validation and API errors in English in either display language", async () => {
    // 入力検証と通信の失敗は日本語画面でも英語で表示し、切替時に再提出しない。
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    fetchMock.mockImplementation((url, options) => {
      if (url === `${SOJ_URL}/api/v3/submissions`) {
        return Promise.resolve({ ok: false, status: 503, json: async () => ({}) });
      }
      return defaultFetchResponse(url, options);
    });
    renderPlayground();
    await screen.findByText(/日本語の問題文1/);
    fireEvent.click(runButton());
    expect(document.querySelector("#result-text")?.textContent).toBe("No input provided");
    fireEvent.click(screen.getByRole("button", { name: "Test English" }));
    expect(document.querySelector("#result-text")?.textContent).toBe("No input provided");

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "true" } });
    fireEvent.click(runButton());
    await waitFor(() => {
      expect(document.querySelector("#result-text")?.textContent).toBe(
        "Error: HTTP error! status: 503",
      );
    });
    const callsBeforeSwitch = fetchMock.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Test Japanese" }));
    expect(document.querySelector("#result-text")?.textContent).toBe(
      "Error: HTTP error! status: 503",
    );
    expect(fetchMock).toHaveBeenCalledTimes(callsBeforeSwitch);
  });

  test("shows expected images only for image problems and no result placeholder", async () => {
    // 通常問題と未実行結果では画像領域を作らず、画像カテゴリの問題だけに想定画像を表示する。
    renderPlayground();
    await screen.findByText(/日本語の問題文1/);
    expect(document.querySelector("#expected-image")).not.toBeInTheDocument();
    expect(document.querySelector("#result-image")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/問題を選ぶ/).closest("summary"));
    fireEvent.click(screen.getByRole("button", { name: /^画像/ }));
    fireEvent.click(await screen.findByRole("button", { name: /画像問題1/ }));

    await waitFor(() => {
      expect(document.querySelector("#expected-image")).toHaveAttribute(
        "src",
        `${SOJ_URL}/image/${IMAGE_PROBLEM_ID}.jpg`,
      );
    });
    expect(document.querySelector("#result-image")).not.toBeInTheDocument();
  });
});
