import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { LanguageProvider } from "./language";
import HelpDetails from "./tsx/help_details";

afterEach(() => {
  // 保存した表示言語を後続の画面テストへ持ち越さない。
  localStorage.clear();
});

test.each(["ja", "en"])("closes only its own help panel and restores focus in %s", (language) => {
  // 末尾から閉じても他の欄・子要素の入力を保持し、見出しから再び開けることを確認する。
  localStorage.setItem("soj-language", language);
  render(
    <LanguageProvider>
      <HelpDetails summary="Help 1">
        <label>
          Memo
          <input defaultValue="keep" />
        </label>
      </HelpDetails>
      <HelpDetails summary="Help 2">Another panel</HelpDetails>
    </LanguageProvider>,
  );
  const first = screen.getByText("Help 1");
  const second = screen.getByText("Help 2");
  fireEvent.click(first);
  fireEvent.click(second);
  fireEvent.change(screen.getByLabelText("Memo"), { target: { value: "edited" } });
  const close = screen.getByRole("button", {
    name: language === "ja" ? "Help 1を閉じる" : "Close Help 1",
  });
  expect(close).toHaveTextContent(language === "ja" ? "閉じる" : "Close");
  expect(close).toHaveAttribute("type", "button");
  fireEvent.click(close);
  expect(first.closest("details").open).toBe(false);
  expect(second.closest("details").open).toBe(true);
  expect(document.activeElement).toBe(first);
  fireEvent.click(first);
  expect(first.closest("details").open).toBe(true);
  expect(screen.getByLabelText("Memo")).toHaveValue("edited");
});
