// @vitest-environment node
import { createRequire } from "node:module";
import { describe, expect, it } from "vitest";
import { Minimatch, minimatch } from "minimatch";

const implementations = [
  ["ESM", { Minimatch, minimatch }],
  ["CommonJS", createRequire(import.meta.url)("minimatch")],
];

describe.each(implementations)("minimatch %s", (_name, api) => {
  // 小さい展開上限でも前処理がそれを守ることを、大量入力なしで確認する。
  it("limits globstar-parent expansion to the configured budget", () => {
    const matcher = new api.Minimatch("**/../alpha/**/../beta/**/../gamma", {
      optimizationLevel: 2,
      braceExpandMax: 2,
    });
    expect(matcher.set.length).toBeGreaterThan(0);
    expect(matcher.set.length).toBeLessThanOrEqual(2);
  });

  // ESLintの拡張子・dotfile・否定patternと通常の対象外fileの境界を確認する。
  it.each([
    ["src/app.tsx", "src/**/*.{js,jsx,ts,tsx}", { dot: true }, true],
    ["src/nested/app.js", "src/**/*.{js,jsx,ts,tsx}", { dot: true }, true],
    ["src/.hidden.ts", "src/**/*.{js,jsx,ts,tsx}", { dot: true }, true],
    ["src/app.css", "src/**/*.{js,jsx,ts,tsx}", { dot: true }, false],
    ["public/app.ts", "src/**/*.{js,jsx,ts,tsx}", { dot: true }, false],
    ["tools.cjs", "**/*.cjs", { dot: true }, true],
    ["dist/assets/app.js", "!dist/**", { dot: true, flipNegate: true }, true],
    ["src/app.js", "!dist/**", { dot: true, flipNegate: true }, false],
  ])("preserves matching %s against %s", (path, pattern, options, expected) => {
    expect(api.minimatch(path, pattern, options)).toBe(expected);
    expect(new api.Minimatch(pattern, options).match(path)).toBe(expected);
  });

  // directory探索で途中階層を誤って除外せず、無関係なdirectoryは除外する。
  it("preserves partial directory matching and the original pattern", () => {
    const pattern = "src/**/*.{js,jsx,ts,tsx}";
    const matcher = new api.Minimatch(pattern, { dot: true });
    expect(matcher.pattern).toBe(pattern);
    expect(matcher.match("src/nested", true)).toBe(true);
    expect(matcher.match("public", true)).toBe(false);
  });
});
