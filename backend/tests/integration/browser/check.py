"""test専用container内のChromiumで実frontendの提出と表示を検証する。"""

import json
import os

# 任意group未導入でも通常の型検査を妨げず、導入時には実際の型情報で検査する。
from playwright.sync_api import Page, expect, sync_playwright  # type: ignore[import-not-found]


def submit(page: Page, command: str, verdict: str, label: str) -> int:
    """実ボタンから提出し、HTTP結果・表示・保存IDとボタンの操作可否を確認する。"""
    page.locator("#cmdline").fill(command)
    # 実rate limitの枠を前の提出と共有するため、操作間隔を確保する。
    page.wait_for_timeout(1100)
    with page.expect_response(
        lambda response: "/api/v3/submissions" in response.url
    ) as pending:
        page.locator("#submit-button").click()
    response = pending.value
    assert response.status == 200
    result = response.json()
    assert result["verdict"] == verdict
    assert result["persistence"] == "saved"
    expect(page.locator("#result-text")).to_contain_text(label)
    expect(page.locator("#submit-button")).to_be_enabled()
    return int(result["submission_id"])


def main() -> None:
    """外部通信・mockなしでtext、実行失敗、画像の表示を検証し、保存IDだけを出力する。"""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        # 一時自己署名証明書のみ例外扱い。ホスト側HTTP testはCA検証も実施する。
        page = browser.new_page(ignore_https_errors=True)
        page.set_default_timeout(45000)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("https://frontend/", wait_until="networkidle")
        ids = [submit(page, "echo test", "accepted", "正解 / Correct")]
        expect(page.locator("#user-output-text")).to_contain_text("test")
        ids.append(submit(page, "printf wrong", "wrong_answer", "不正解 / Incorrect"))
        ids.append(
            submit(page, "sleep 20", "execution_failure", "実行がタイムアウトしました")
        )
        ids.append(
            submit(page, "seq 1 2000", "execution_failure", "出力上限を超えました")
        )
        page.get_by_role("button", name="画像問題 / IMAGE", exact=True).click()
        page.locator("tr").filter(has_text="IMAGE-00000001").click()
        detail = page.request.get("https://frontend/api/problems/IMAGE-00000001").json()
        ids.append(submit(page, detail["answer"], "accepted", "正解 / Correct"))
        expect(page.locator("img#result-image")).to_be_visible()
        assert page.locator("img#result-image").evaluate(
            "image => image.complete && image.naturalWidth > 0"
        )
        page.get_by_role("link", name="ABOUT & INFO", exact=True).click()
        expect(
            page.get_by_text(
                f"version: {os.environ['SOJ_EXPECTED_VERSION']}", exact=True
            )
        ).to_be_visible()
        assert not errors
        browser.close()
        print(json.dumps({"submission_ids": ids}))


if __name__ == "__main__":
    main()
