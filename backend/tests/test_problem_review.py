"""差分による画面検査の縮小と、安全側への全件復帰を検査する。"""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from soj_tools import problem_review as review

AVAILABLE = [
    *review.REPRESENTATIVES,
    "STANDARD-00000065",
    "IMAGE-00000001",
    "REGEX-00000001",
]


def test_data_only_changes_include_changed_problems_and_representatives() -> None:
    # YAMLと画像の同一IDを重複させず、新問と共通の空白・カテゴリ検査を選ぶ。
    paths = [
        "problems/v3/STANDARD-00000065.yaml",
        "problems/image/STANDARD-00000065.jpg",
        "problems/v3/manifest.json",
        "docs/problem-design-notes.md",
        "backend/tests/test_pending_tasks_problem.py",
        "backend/tests/integration/test_pending_tasks_solutions.py",
    ]
    selection = review.selection_for_paths(paths, AVAILABLE)
    assert json.loads(selection) == ["STANDARD-00000065"]
    assert review.select_problem_ids(AVAILABLE, selection) == sorted(
        [*review.REPRESENTATIVES, "STANDARD-00000065"]
    )


def test_markdown_only_changes_check_only_representatives() -> None:
    # repository直下やcomponent配下の文書だけの変更は、代表例だけの画面検査へ縮小する。
    paths = [
        "AGENTS.md",
        "README.md",
        "SECURITY.md",
        "backend/README.md",
        "backend/tests/integration/README.md",
        "frontend/README.md",
        "docs/CI.md",
    ]
    selection = review.selection_for_paths(paths, AVAILABLE)
    assert json.loads(selection) == []
    assert review.select_problem_ids(AVAILABLE, selection) == sorted(
        review.REPRESENTATIVES
    )


@pytest.mark.parametrize(
    "path",
    [
        "frontend/src/tsx/problem.tsx",
        "frontend/src/content/notes.md",
        "frontend/public/notes.md",
        "docs/diagram.svg",
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
    # 共通実装・検査基盤・frontend取り込み対象・削除・未知fileを新問だけの検査へ縮小しない。
    assert review.selection_for_paths([path], AVAILABLE) == "all"
    assert review.selection_for_paths([], AVAILABLE) == "all"


@pytest.mark.parametrize(
    "selection",
    ["null", "{}", "[3]", '["missing"]', '["STANDARD-00000065", "STANDARD-00000065"]'],
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
            args, 0, "problems/v3/STANDARD-00000065.yaml\0"
        )

    monkeypatch.setattr(review.subprocess, "run", run)
    assert review.github_selection() == '["STANDARD-00000065"]'

    def unavailable(*args: object, **kwargs: object) -> None:
        # shallow履歴などの取得不能を成功扱いで省略しない。
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(review.subprocess, "run", unavailable)
    assert review.github_selection() == "all"
    event.write_text(json.dumps({"before": "0" * 40}))
    assert review.github_selection() == "all"


def test_full_review_shards_cover_every_problem_once() -> None:
    # 全件modeの正規表現・詳細検査を分割しても、各問題をちょうど1つのshardで検査する。
    available = [
        *AVAILABLE,
        "REGEX-00000002",
        "REGEX-00000003",
        "STANDARD-00000075",
        "STANDARD-00000066",
    ]
    shards = review.shards_for("all")
    assert shards == [f"{i}/{review.FULL_REVIEW_SHARDS}" for i in range(3)]
    plans = [review.browser_plan(available, "all", shard) for shard in shards]
    regex = [pid for plan in plans for pid in plan[0]]
    detail = [pid for plan in plans for pid in plan[1]]
    assert sorted(regex) == sorted(p for p in available if p.startswith("REGEX-"))
    assert sorted(detail) == sorted(p for p in available if not p.startswith("REGEX-"))
    assert len(regex) == len(set(regex)) and len(detail) == len(set(detail))


def test_selected_review_runs_in_one_unsplit_job() -> None:
    # 変更問題だけの検査は1 jobで代表例と正規表現代表1問を含め、分割指定を拒否する。
    selection = '["STANDARD-00000065"]'
    assert review.shards_for(selection) == ["0/1"]
    regex, detail = review.browser_plan(AVAILABLE, selection)
    assert regex == ["REGEX-00000001"]
    assert detail == sorted([*review.REPRESENTATIVES, "STANDARD-00000065"])
    with pytest.raises(ValueError):
        review.browser_plan(AVAILABLE, selection, "1/3")


@pytest.mark.parametrize("shard", ["", "1", "3/3", "-1/3", "0/0", "a/b", "0/3 "])
def test_invalid_shard_is_rejected(shard: str) -> None:
    # 担当外の問題を黙って検査しないよう、範囲外や不正形式のshardは失敗させる。
    with pytest.raises(ValueError):
        review.shard_ids(["REGEX-00000001"], shard)


def test_main_writes_selection_and_shards_to_job_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # job outputへ選択とmatrix用shard一覧をJSON一行ずつ書く。
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(review, "github_selection", lambda: "all")
    monkeypatch.setattr(sys, "argv", ["problem_review.py", "--github-output"])
    review.main()
    assert output.read_text() == (
        'browser_selection=all\nbrowser_shards=["0/3", "1/3", "2/3"]\n'
    )
