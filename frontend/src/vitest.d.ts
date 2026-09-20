import "vitest";
import type { TestingLibraryMatchers } from "@testing-library/jest-dom/matchers";

declare module "vitest" {
  // Vitest 5の戻り値R（同期void・非同期Promise<void>）をDOM matcherにも引き継ぐ。
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type -- 宣言マージで公開matcher型を追加する。
  interface Matchers<R, T> extends TestingLibraryMatchers<T, R> {}
}
