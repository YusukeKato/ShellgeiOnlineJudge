import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test } from "vitest";

import App from "./tsx/App.tsx";

beforeEach(() => {
  // 共通headerと案内画面は日本語から開始し、保存済み設定に依存させない。
  localStorage.clear();
});

afterEach(() => {
  // この画面テストが作成した言語設定とrouteを片付ける。
  localStorage.clear();
  window.history.pushState({}, "", "/");
});

test("renders", () => {
  // application全体が起動し、共通footerまで表示されることを確認する。
  window.history.pushState({}, "", "/about");
  try {
    render(<App />);
    const linkElement = screen.getByText(/2023 YusukeKato All rights reserved./i);
    expect(linkElement).toBeInTheDocument();
  } finally {
    window.history.pushState({}, "", "/");
  }
});

test("switches the shared navigation language and preserves the contact form link", () => {
  // 共通headerの言語操作で案内画面が切り替わり、問い合わせ先は同じ別タブリンクを維持する。
  window.history.pushState({}, "", "/about");
  render(<App />);
  const header = screen.getByRole("banner");
  expect(within(header).getByRole("link", { name: "使い方・情報" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(within(header).getByRole("button", { name: "日本語" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  fireEvent.click(within(header).getByRole("button", { name: "English" }));

  expect(within(header).getByRole("link", { name: "About" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(within(header).getByRole("button", { name: "English" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(document.documentElement).toHaveAttribute("lang", "en");
  expect(localStorage.getItem("soj-language")).toBe("en");
  const forms = document.querySelectorAll(
    'a[href="https://docs.google.com/forms/d/e/1FAIpQLSe8XIueiVyEXZBlVzwTYzqF241MLRkYK17PCtKy8Y94Fs7z1A/viewform?usp=dialog"]',
  );
  expect(forms.length).toBeGreaterThan(0);
  for (const form of forms) {
    expect(form).toHaveAttribute("target", "_blank");
    expect(form.rel).toContain("noopener");
    expect(form.rel).toContain("noreferrer");
  }
});
