import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import Playground from "./tsx/playground";

const SOJ_URL = "https://soj.example";
const DEFAULT_PROBLEM_ID = "STANDARD-00000001";
const SECOND_PROBLEM_ID = "STANDARD-00000002";

const problemListResponse = () => ({
  // 2問を含む問題一覧responseを返し、初期選択と選択raceのテストで共用する。
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
    fetchMock.mockImplementation(defaultFetchResponse);
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      writable: true,
      value: fetchMock,
    });
  });

  afterEach(() => {
    // 呼び出し履歴とmock実装を破棄し、後続テストへ通信状態を持ち越さない。
    fetchMock.mockReset();
  });

  test("selects and loads standard problem 1 on the initial render", async () => {
    // 利用者が操作しなくても標準問題1番が選択され、その問題詳細と選択行が表示されることを確認する。
    render(<Playground soj_url={SOJ_URL} />);

    expect(document.querySelector("#selected-text")?.textContent).toBe(DEFAULT_PROBLEM_ID);
    expect(await screen.findByText(/日本語の問題文1/)).toBeInTheDocument();
    expect(document.querySelector(".problem-table tr.selected-row")?.textContent).toContain(
      DEFAULT_PROBLEM_ID,
    );
  });

  test("submits standard problem 1 without an explicit problem click", async () => {
    // 初期状態のままコマンドを実行した場合も、有効な標準問題1番のIDが投稿APIへ送られることを確認する。
    render(<Playground soj_url={SOJ_URL} />);

    fireEvent.change(screen.getByPlaceholderText(/Type your shell one-liner here/), {
      target: { value: "printf ok" },
    });
    fireEvent.click(screen.getByDisplayValue(/RUN/));

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
    render(<Playground soj_url={SOJ_URL} />);
    await screen.findByText(/日本語の問題文1/);
    fireEvent.change(screen.getByPlaceholderText(/Type your shell one-liner here/), {
      target: { value: "sleep 1" },
    });

    fireEvent.click(screen.getByDisplayValue(/RUN/));
    fireEvent.click(screen.getByDisplayValue(/RUN/));

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
    render(<Playground soj_url={SOJ_URL} />);
    await screen.findByText(/日本語の問題文1/);
    const input = screen.getByPlaceholderText(/Type your shell one-liner here/);

    fireEvent.change(input, { target: { value: "printf first" } });
    fireEvent.click(screen.getByDisplayValue(/RUN/));
    fireEvent.change(input, { target: { value: "printf second" } });
    fireEvent.click(screen.getByDisplayValue(/RUN/));

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
    render(<Playground soj_url={SOJ_URL} />);
    fireEvent.click(await screen.findByText(/標準問題2 \/ Standard problem 2/));

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
});
