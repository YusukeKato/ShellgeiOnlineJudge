import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import App from "./tsx/App.tsx";

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
