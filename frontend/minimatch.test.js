// @vitest-environment node
import { createRequire } from "node:module";
import { describe, expect, it } from "vitest";
import { Minimatch, minimatch, escape } from "minimatch";

const implementations = [
  ["ESM", { Minimatch, minimatch, escape }],
  ["CommonJS", createRequire(import.meta.url)("minimatch")],
];

describe.each(implementations)("minimatch %s", (_name, api) => {
  // 小さい上限内の通常patternを受理し、上限を越える展開は明示的に拒否する。
  it("limits globstar-parent expansion to the configured budget", () => {
    const matcher = new api.Minimatch("**/../alpha", {
      optimizationLevel: 2,
      braceExpandMax: 2,
    });
    expect(matcher.set.length).toBeGreaterThan(0);
    expect(matcher.set.length).toBeLessThanOrEqual(2);
  });

  it("rejects globstar-parent expansion above the configured budget", () => {
    expect(
      () =>
        new api.Minimatch("**/../alpha/**/../beta/**/../gamma", {
          optimizationLevel: 2,
          braceExpandMax: 2,
        }),
    ).toThrow(RangeError);
  });

  // escape後の先頭記号を否定・commentとして解釈せず、無関係なfileにも一致させない。
  it.each([
    ["!draft.txt", {}],
    ["#draft.txt", {}],
    ["file{a,b}.txt", { magicalBraces: true }],
    ["file[1].txt", {}],
  ])("matches escaped literal %s without changing its meaning", (literal, options) => {
    const pattern = api.escape(literal, options);
    expect(api.minimatch(literal, pattern, options)).toBe(true);
    expect(new api.Minimatch(pattern, options).match(literal)).toBe(true);
    expect(api.minimatch("unrelated.txt", pattern, options)).toBe(false);
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
