import { expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

// jest-domの旧Assertion型を取り込まず、公開matcherを全testのexpectへ登録する。
// Vitest 5用の型拡張はvitest.d.tsで管理する。
expect.extend(matchers);
