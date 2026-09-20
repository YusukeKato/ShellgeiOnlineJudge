import { expect, expectTypeOf, test } from "vitest";

test("DOM matchers preserve synchronous return types and reject mismatches", () => {
  // 実DOMの一致・不一致を検証し、同期matcherがvoidを返す型契約も確認する。
  const element = document.createElement("button");
  element.textContent = "Run";
  element.disabled = true;

  expectTypeOf(expect(element).toHaveTextContent("Run")).toEqualTypeOf<void>();
  expect(element).toBeDisabled();
  expect(element).not.toHaveTextContent("Stop");
  expect(() => expect(element).toHaveTextContent("Stop")).toThrow();
});

test("DOM matchers preserve awaited return types", async () => {
  // resolves・rejects経由でもDOM検証を実行し、戻り値がPromise<void>になることを確認する。
  const element = document.createElement("button");
  element.textContent = "Run";
  element.disabled = true;

  const resolved = expect(Promise.resolve(element)).resolves.toHaveTextContent("Run");
  expectTypeOf(resolved).toEqualTypeOf<Promise<void>>();
  await resolved;
  await expect(Promise.reject(element)).rejects.toBeDisabled();
  await expect(
    expect(Promise.resolve(element)).resolves.toHaveTextContent("Stop"),
  ).rejects.toThrow();
});
