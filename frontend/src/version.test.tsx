import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import release from "../../backend/soj_shared/version.json";
import App from "./tsx/App";

afterEach(() => {
  vi.unstubAllEnvs();
  window.history.replaceState({}, "", "/");
});

// 古い.envのversion指定があっても、画面はビルド対象の正本versionを表示する。
it("shows the canonical release version on the about page", () => {
  vi.stubEnv("VITE_VERSION", "0.0.0-stale");
  window.history.replaceState({}, "", "/about");
  render(<App />);
  expect(screen.getByText(`version: ${release.version}`)).toBeInTheDocument();
  expect(screen.queryByText("version: 0.0.0-stale")).not.toBeInTheDocument();
});
