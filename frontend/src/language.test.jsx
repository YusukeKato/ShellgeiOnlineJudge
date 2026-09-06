import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { LanguageProvider, useLanguage } from "./language";

const LanguageExample = () => {
  // providerの表示切替と保存を同じ利用操作から確認し、画面固有の文言に依存しない。
  const { text, setLanguage } = useLanguage();
  return (
    <>
      <p>{text("問題を解く", "Solve problems")}</p>
      <button onClick={() => setLanguage("ja")}>日本語</button>
      <button onClick={() => setLanguage("en")}>English</button>
    </>
  );
};

const renderLanguage = () => {
  // 本番と同じproviderから初期言語を読み、子componentを描画する。
  return render(
    <LanguageProvider>
      <LanguageExample />
    </LanguageProvider>,
  );
};

beforeEach(() => {
  // 保存値とhtml属性を初期化し、別テストの表示言語を持ち越さない。
  localStorage.clear();
  document.documentElement.lang = "";
});

afterEach(() => {
  // storage障害のspyを解除してから、今回作成した設定だけを片付ける。
  vi.restoreAllMocks();
  localStorage.clear();
  document.documentElement.lang = "ja";
});

test.each([null, "fr", "EN", "<script>alert(1)</script>"])(
  "defaults to Japanese for a missing or unsupported saved language: %s",
  (stored) => {
    // 未設定・対応外の保存値を日本語へ戻し、DOMのlangにも未検証文字列を使用しない。
    if (stored !== null) {
      localStorage.setItem("soj-language", stored);
    }
    renderLanguage();

    expect(screen.getByText("問題を解く")).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("lang", "ja");
    expect(localStorage.getItem("soj-language")).toBe("ja");
  },
);

test("restores and persists the selected language across a fresh mount", () => {
  // 保存済み英語で開始し、日本語への操作を保存して次回表示にも引き継ぐ。
  localStorage.setItem("soj-language", "en");
  const first = renderLanguage();

  expect(screen.getByText("Solve problems")).toBeInTheDocument();
  expect(document.documentElement).toHaveAttribute("lang", "en");
  fireEvent.click(screen.getByRole("button", { name: "日本語" }));
  expect(screen.getByText("問題を解く")).toBeInTheDocument();
  expect(document.documentElement).toHaveAttribute("lang", "ja");
  expect(localStorage.getItem("soj-language")).toBe("ja");
  first.unmount();
  renderLanguage();
  expect(screen.getByText("問題を解く")).toBeInTheDocument();
});

test("allows language changes when reading and writing storage are blocked", () => {
  // browserが設定保存を拒否しても初期描画と画面内の言語変更が動作し、htmlのlangも更新する。
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new DOMException("Storage blocked", "SecurityError");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new DOMException("Storage blocked", "SecurityError");
  });
  renderLanguage();

  expect(screen.getByText("問題を解く")).toBeInTheDocument();
  expect(document.documentElement).toHaveAttribute("lang", "ja");
  fireEvent.click(screen.getByRole("button", { name: "English" }));
  expect(screen.getByText("Solve problems")).toBeInTheDocument();
  expect(document.documentElement).toHaveAttribute("lang", "en");
  fireEvent.click(screen.getByRole("button", { name: "日本語" }));
  expect(screen.getByText("問題を解く")).toBeInTheDocument();
});
