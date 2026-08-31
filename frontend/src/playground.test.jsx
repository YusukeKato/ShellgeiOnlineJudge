import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import Playground from "./tsx/playground";

const SOJ_URL = "https://soj.example";
const DEFAULT_PROBLEM_ID = "STANDARD-00000001";

describe("playground default problem", () => {
  const fetchMock = jest.fn();

  beforeEach(() => {
    // 問題一覧・問題詳細・投稿APIをURL別に応答させ、初期表示と送信内容を外部通信なしで確認する。
    fetchMock.mockImplementation(async (url, options) => {
      if (url === `${SOJ_URL}/api/problems`) {
        return {
          ok: true,
          json: async () => [
            {
              id: DEFAULT_PROBLEM_ID,
              category: "STANDARD",
              title_ja: "標準問題1",
              title_en: "Standard problem 1",
            },
          ],
        };
      }
      if (url === `${SOJ_URL}/api/problems/${DEFAULT_PROBLEM_ID}`) {
        return {
          ok: true,
          json: async () => ({
            title_ja: "標準問題1",
            statement_ja: "日本語の問題文",
            title_en: "Standard problem 1",
            statement_en: "English statement",
            input: "入力例",
            expected_output: "出力例",
            image: `/image/${DEFAULT_PROBLEM_ID}.jpg`,
          }),
        };
      }
      if (url === `${SOJ_URL}/api/shellgei` && options?.method === "POST") {
        return {
          ok: true,
          json: async () => ({
            output: "ok",
            id: "1",
            date: "2026-09-01 00:00:00",
            judge: "1",
            image: "",
            image_media_type: null,
          }),
        };
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
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
    expect(await screen.findByText(/日本語の問題文/)).toBeInTheDocument();
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
      expect(fetchMock).toHaveBeenCalledWith(`${SOJ_URL}/api/shellgei`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shellgei: "printf ok",
          problem_id: DEFAULT_PROBLEM_ID,
        }),
      });
    });
  });
});
