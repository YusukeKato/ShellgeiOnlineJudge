// @vitest-environment node
import { createHash } from "node:crypto";
import { afterEach, describe, expect, it } from "vitest";
import { fetch, MockAgent } from "undici";

let agent;
afterEach(async () => {
  await agent?.close();
});

describe("Undiciの修正版と通常取得の互換性", () => {
  it("SRIの末尾のASCII空白を許可し、内容hashが一致する本文を返す", async () => {
    // 実ネットワークを禁止した短い固定応答で、integrity metadataの空白処理を確認する。
    agent = new MockAgent();
    agent.disableNetConnect();
    agent.get("https://source.invalid").intercept({ path: "/body" }).reply(200, "SOJ");
    const digest = createHash("sha256").update("SOJ").digest("base64");
    const response = await fetch("https://source.invalid/body", {
      dispatcher: agent,
      integrity: "sha256-" + digest + " \t\n",
    });
    expect(await response.text()).toBe("SOJ");
    agent.assertNoPendingInterceptors();
  });

  it("別originへのredirectでAuthorizationを転送せず、通常の本文を取得する", async () => {
    // 公開先に接続せず、架空の2origin間だけでheaderの境界を確認する。
    agent = new MockAgent();
    agent.disableNetConnect();
    agent
      .get("https://source.invalid")
      .intercept({ path: "/redirect" })
      .reply(302, "", { headers: { location: "https://target.invalid/final" } });
    let received;
    agent
      .get("https://target.invalid")
      .intercept({ path: "/final" })
      .reply((options) => {
        received = new Headers(options.headers).get("authorization");
        return { statusCode: 200, data: "complete" };
      });
    const response = await fetch("https://source.invalid/redirect", {
      dispatcher: agent,
      headers: { authorization: "Bearer synthetic-test-only" },
    });
    expect(await response.text()).toBe("complete");
    expect(received).toBeNull();
    agent.assertNoPendingInterceptors();
  });
});
