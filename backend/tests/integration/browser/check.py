"""test専用container内のChromiumで実frontendの提出と表示を検証する。"""

import json
import os
import re
from pathlib import Path

# 任意group未導入でも通常の型検査を妨げず、導入時には実際の型情報で検査する。
from playwright.sync_api import Page, expect, sync_playwright  # type: ignore[import-not-found]

VIEWPORT_WIDTHS = (320, 375, 390, 430, 768, 1024, 1440)
CONTACT_FORM_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSe8XIueiVyEXZBlVzwTYzqF241MLRkYK17PCtKy8Y94Fs7z1A/viewform?usp=dialog"
)


def switch_language(page: Page, language: str) -> None:
    """共通headerから表示言語を選び、選択状態・html属性・設定保存を確認する。"""
    button = page.get_by_role("banner").get_by_role(
        "button", name="日本語" if language == "ja" else "English", exact=True
    )
    button.click()
    expect(button).to_have_attribute("aria-pressed", "true")
    expect(page.locator("html")).to_have_attribute("lang", language)
    assert page.evaluate("localStorage.getItem('soj-language')") == language


def assert_page_width(page: Page) -> None:
    """全体の横スクロールが発生せず、headerと本文を現在の画面幅で操作できることを確認する。"""
    assert page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth + 1"
    ), f"page overflows at {page.viewport_size}"
    expect(page.get_by_role("banner")).to_be_visible()
    expect(
        page.get_by_role("banner").get_by_role("button", name="English")
    ).to_be_visible()


def capture_result_screenshots(page: Page) -> None:
    """実際の正解結果をPCの日英・スマートフォン日本語で保存し、元の表示へ戻す。"""
    directory = Path("/tmp/soj-ui")
    directory.mkdir(parents=True, exist_ok=True)
    original_viewport = page.viewport_size
    try:
        page.set_viewport_size({"width": 1440, "height": 1000})
        for language in ("ja", "en"):
            switch_language(page, language)
            page.screenshot(
                path=directory / f"desktop-{language}.png",
                full_page=True,
                animations="disabled",
            )
        page.set_viewport_size({"width": 390, "height": 844})
        switch_language(page, "ja")
        page.screenshot(
            path=directory / "mobile-ja.png", full_page=True, animations="disabled"
        )
    finally:
        switch_language(page, "ja")
        if original_viewport is not None:
            page.set_viewport_size(original_viewport)


def check_problem_picker(page: Page, language: str) -> None:
    """狭い画面でも各カテゴリを開け、選択済み問題を変更せず閉じられることを確認する。"""
    problem_id = page.locator("#selected-text").inner_text()
    picker = page.locator("details.problem-picker")
    summary = picker.locator("summary")
    expect(summary).to_contain_text(
        "問題を選ぶ" if language == "ja" else "Choose problem"
    )
    summary.click()
    expect(picker).to_have_attribute("open", "")
    categories = (
        ("通常", "練習", "画像")
        if language == "ja"
        else ("Standard", "Practice", "Image")
    )
    for category in categories:
        button = picker.get_by_role("button", name=category, exact=True)
        button.click()
        expect(button).to_have_attribute("aria-pressed", "true")
        expect(picker.locator(".problem-option").first).to_be_visible()
        assert_page_width(page)
    summary.click()
    expect(picker).not_to_have_attribute("open", "")
    expect(page.locator("#selected-text")).to_have_text(problem_id)


def check_responsive_playground(page: Page) -> None:
    """実結果を保持して日英・7画面幅を検証し、長いコードのoverflowを局所に限定する。"""
    input_code = page.locator("#input-text")
    output_code = page.locator("#user-output-text")
    original_input = input_code.text_content()
    original_output = output_code.text_content()
    original_command = page.locator("#cmdline").input_value()
    long_line = "0123456789" * 100
    # 表示だけのfixtureを一時注入し、追加提出や判定データの変更を行わない。
    input_code.evaluate("(node, value) => { node.textContent = value; }", long_line)
    output_code.evaluate("(node, value) => { node.textContent = value; }", long_line)
    page.locator("#cmdline").fill(long_line)
    try:
        for width in VIEWPORT_WIDTHS:
            page.set_viewport_size({"width": width, "height": 900})
            for language in ("ja", "en"):
                switch_language(page, language)
                assert_page_width(page)
                expect(page.locator("#cmdline")).to_have_value(long_line)
                for code in (input_code, output_code):
                    bounds = code.evaluate(
                        """node => {
                            const pre = node.closest('pre');
                            const box = pre.getBoundingClientRect();
                            return {
                                left: box.left, right: box.right,
                                width: window.innerWidth,
                                client: pre.clientWidth, scroll: pre.scrollWidth,
                                overflow: getComputedStyle(pre).overflowX
                            };
                        }"""
                    )
                    assert bounds["left"] >= -1
                    assert bounds["right"] <= bounds["width"] + 1
                    if bounds["scroll"] > bounds["client"] + 1:
                        assert bounds["overflow"] in {"auto", "scroll"}
                check_problem_picker(page, language)
    finally:
        input_code.evaluate(
            "(node, value) => { node.textContent = value; }", original_input
        )
        output_code.evaluate(
            "(node, value) => { node.textContent = value; }", original_output
        )
        page.locator("#cmdline").fill(original_command)


def check_about_page(page: Page) -> None:
    """案内画面も日英・各画面幅で操作でき、問い合わせ先と正本versionを維持することを確認する。"""
    page.get_by_role("banner").get_by_role("link", name="About", exact=True).click()
    for width in VIEWPORT_WIDTHS:
        page.set_viewport_size({"width": width, "height": 900})
        for language in ("ja", "en"):
            switch_language(page, language)
            assert_page_width(page)
            expect(
                page.get_by_role("main").get_by_role("heading", level=1)
            ).to_be_visible()
            expect(
                page.get_by_text(
                    f"version: {os.environ['SOJ_EXPECTED_VERSION']}", exact=True
                )
            ).to_be_visible()
            forms = page.locator(f'a[href="{CONTACT_FORM_URL}"]')
            assert forms.count() > 0
            for form in forms.all():
                expect(form).to_be_visible()
                expect(form).to_have_attribute("target", "_blank")
                expect(form).to_have_attribute("rel", re.compile(r"\bnoopener\b"))
                expect(form).to_have_attribute("rel", re.compile(r"\bnoreferrer\b"))


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
        submissions: list[str] = []
        page.on(
            "request",
            lambda request: submissions.append(request.url)
            if request.method == "POST" and "/api/v3/submissions" in request.url
            else None,
        )
        expect(page.locator("html")).to_have_attribute("lang", "ja")
        expect(page.locator("#result-image")).to_have_count(0)
        expect(page.locator("#expected-image")).to_have_count(0)
        ids = [submit(page, "echo test", "accepted", "正解")]
        expect(page.locator("#user-output-text")).to_contain_text("test")
        capture_result_screenshots(page)
        # 表示切替だけで入力・結果・対象問題が変わらず、再提出も発生しないことを確認する。
        selected = page.locator("#selected-text").inner_text()
        page.locator("#cmdline").fill("printf '次の入力'")
        for language, label in (("en", "Accepted"), ("ja", "正解"), ("en", "Accepted")):
            switch_language(page, language)
            expect(page.locator("#cmdline")).to_have_value("printf '次の入力'")
            expect(page.locator("#selected-text")).to_have_text(selected)
            expect(page.locator("#result-text")).to_have_text(label)
            expect(page.locator("#user-output-text")).to_contain_text("test")
            expect(page.locator("#shellgei-text")).to_contain_text("echo test")
        assert len(submissions) == 1
        page.reload(wait_until="networkidle")
        expect(page.locator("html")).to_have_attribute("lang", "en")
        expect(page.locator("#result-text")).to_have_text("Not run yet")
        switch_language(page, "ja")
        ids.append(submit(page, "printf wrong", "wrong_answer", "不正解"))
        ids.append(
            submit(
                page,
                "sleep 20",
                "execution_failure",
                "Execution failed: Execution timed out",
            )
        )
        ids.append(
            submit(
                page,
                "seq 1 2000",
                "execution_failure",
                "Execution failed: Output limit exceeded",
            )
        )
        page.locator("details.problem-picker summary").click()
        page.get_by_role("button", name="画像", exact=True).click()
        page.get_by_role("button", name=re.compile("IMAGE-00000001")).click()
        expect(page.locator("#selected-text")).to_have_text("IMAGE-00000001")
        expect(page.locator("#expected-image")).to_be_visible()
        detail = page.request.get("https://frontend/api/problems/IMAGE-00000001").json()
        ids.append(submit(page, detail["answer"], "accepted", "正解"))
        expect(page.locator("img#result-image")).to_be_visible()
        page.wait_for_function(
            """() => {
                const image = document.querySelector('img#result-image');
                return image && image.complete && image.naturalWidth > 0;
            }"""
        )
        check_responsive_playground(page)
        check_about_page(page)
        assert len(submissions) == 5
        assert not errors
        browser.close()
        print(json.dumps({"submission_ids": ids}))


if __name__ == "__main__":
    main()
