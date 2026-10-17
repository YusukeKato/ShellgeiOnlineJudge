"""差分による画面検査の縮小と、安全側への全件復帰を検査する。"""

import json
from pathlib import Path
import subprocess

import pytest

from soj_tools import problem_review as review

AVAILABLE = [
    *review.REPRESENTATIVES,
    "STANDARD-00000074",
    "IMAGE-00000001",
    "REGEX-00000001",
]


def test_data_only_changes_include_changed_problems_and_representatives() -> None:
    # YAMLと画像の同一IDを重複させず、新問と共通の空白・カテゴリ検査を選ぶ。
    paths = [
        "problems/v3/STANDARD-00000074.yaml",
        "problems/image/STANDARD-00000074.jpg",
        "problems/v3/manifest.json",
        "docs/problem-design-notes.md",
        "backend/tests/test_pending_tasks_problem.py",
        "backend/tests/integration/test_pending_tasks_solutions.py",
    ]
    selection = review.selection_for_paths(paths, AVAILABLE)
    assert json.loads(selection) == ["STANDARD-00000074"]
    assert review.select_problem_ids(AVAILABLE, selection) == sorted(
        [*review.REPRESENTATIVES, "STANDARD-00000074"]
    )


@pytest.mark.parametrize(
    "path",
    [
        "frontend/src/tsx/problem.tsx",
        "backend/soj_shared/problem_repository.py",
        "backend/tests/integration/browser/check.py",
        "backend/tests/integration/test_compose_e2e.py",
        ".github/workflows/supply_chain.yaml",
        "deploy/sandbox/Dockerfile",
        "problems/v3/DELETED-01.yaml",
        "problems/v3/odd.txt",
    ],
)
def test_common_changes_or_deleted_problem_require_all_screens(path: str) -> None:
    # 共通実装・検査基盤・削除・未知fileを新問だけの検査へ縮小しない。
    assert review.selection_for_paths([path], AVAILABLE) == "all"
    assert review.selection_for_paths([], AVAILABLE) == "all"


@pytest.mark.parametrize(
    "selection",
    ["null", "{}", "[3]", '["missing"]', '["STANDARD-00000074", "STANDARD-00000074"]'],
)
def test_invalid_explicit_selection_is_not_silently_ignored(selection: str) -> None:
    # 手動指定の誤りで意図した問題を検査し忘れない。
    with pytest.raises(ValueError):
        review.select_problem_ids(AVAILABLE, selection)
    assert review.select_problem_ids(AVAILABLE, "all") == sorted(AVAILABLE)


@pytest.mark.parametrize("event_name", ["schedule", "workflow_dispatch", "unknown"])
def test_periodic_manual_and_unknown_events_check_all(
    monkeypatch: pytest.MonkeyPatch, event_name: str
) -> None:
    # 定期・手動・未知eventでは差分APIやGitへ依存せず全件検査する。
    monkeypatch.setenv("GITHUB_EVENT_NAME", event_name)
    assert review.github_selection() == "all"


@pytest.mark.parametrize("event_name", ["push", "pull_request"])
def test_event_sha_range_and_unavailable_history(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, event_name: str
) -> None:
    # main pushのbeforeとPRのbaseを比較し、Git失敗時は全件へ戻す。
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"before": "a" * 40, "pull_request": {"base": {"sha": "a" * 40}}})
    )
    monkeypatch.setenv("GITHUB_EVENT_NAME", event_name)
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        # SHAをshellに渡さず、削除も分かるno-renamesの差分を取得する。
        assert args == [
            "git",
            "diff",
            "--no-renames",
            "--name-only",
            "-z",
            "a" * 40,
            "b" * 40,
            "--",
        ]
        return subprocess.CompletedProcess(
            args, 0, "problems/v3/STANDARD-00000074.yaml\0"
        )

    monkeypatch.setattr(review.subprocess, "run", run)
    assert review.github_selection() == '["STANDARD-00000074"]'

    def unavailable(*args: object, **kwargs: object) -> None:
        # shallow履歴などの取得不能を成功扱いで省略しない。
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(review.subprocess, "run", unavailable)
    assert review.github_selection() == "all"
    event.write_text(json.dumps({"before": "0" * 40}))
    assert review.github_selection() == "all"
