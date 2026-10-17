"""問題だけの変更を識別し、共通UIと追加・変更問題の画面検査を選ぶ。"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
REPRESENTATIVES = ("PRACTICE-base64-01", "STANDARD-00000068")
PROBLEM_FILE = re.compile(r"problems/(?:v3|image)/([A-Z]+-[A-Za-z0-9-]+)\.(?:yaml|jpg)")


def select_problem_ids(available: list[str], selection: str) -> list[str]:
    """allなら全問題、JSON配列なら代表例を加える。不明ID・重複・不正形式は検査を失敗させる。"""
    if selection == "all":
        return sorted(available)
    requested = json.loads(selection)
    if not isinstance(requested, list) or not all(
        isinstance(x, str) for x in requested
    ):
        raise ValueError("problem selection must be an array of IDs")
    if len(requested) != len(set(requested)) or not set(requested) <= set(available):
        raise ValueError("unknown or duplicate problem ID")
    if not set(REPRESENTATIVES) <= set(available):
        raise ValueError("representative problems are missing")
    return sorted(set(requested) | set(REPRESENTATIVES))


def selection_for_paths(paths: list[str], available: list[str]) -> str:
    """問題data・個別test・文書のみなら変更IDを返し、削除や共通code変更は全件へ戻す。"""
    changed = set()
    for path in paths:
        match = PROBLEM_FILE.fullmatch(path)
        if match:
            if match[1] not in available:
                return "all"
            changed.add(match[1])
        elif path in {
            "problems/v3/manifest.json",
            "problems/README.md",
            "UPDATE_HISTORY.md",
        }:
            continue
        elif path.startswith("docs/") and path.endswith(".md"):
            continue
        elif re.fullmatch(
            r"backend/tests/(?:test_[a-z0-9_]+_problem|integration/test_[a-z0-9_]+_solutions)\.py",
            path,
        ):
            continue
        else:
            return "all"
    return json.dumps(sorted(changed)) if paths else "all"


def github_selection() -> str:
    """eventのSHA範囲をGitで比較する。週次・手動・取得不能・不正SHAは安全側の全件にする。"""
    event_name = os.environ.get("GITHUB_EVENT_NAME")
    if event_name not in {"push", "pull_request"}:
        return "all"
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        base = (
            event["before"]
            if event_name == "push"
            else event["pull_request"]["base"]["sha"]
        )
        head = os.environ["GITHUB_SHA"]
        if not all(
            isinstance(sha, str)
            and re.fullmatch(r"[0-9a-f]{40}", sha)
            and sha != "0" * 40
            for sha in (base, head)
        ):
            return "all"
        result = subprocess.run(
            ["git", "diff", "--no-renames", "--name-only", "-z", base, head, "--"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        available = [p.stem for p in (ROOT / "problems/v3").glob("*.yaml")]
        return selection_for_paths(
            [p for p in result.stdout.split("\0") if p], available
        )
    except (KeyError, ValueError, TypeError, OSError, subprocess.SubprocessError):
        print("Problem diff unavailable; checking all problem screens.")
        return "all"


def main() -> None:
    """GitHub jobへJSON一行の選択値を渡す。shellへevent本文やfile名を展開しない。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-env", action="store_true", required=True)
    parser.parse_args()
    selection = github_selection()
    with Path(os.environ["GITHUB_ENV"]).open("a") as output:
        output.write("SOJ_BROWSER_PROBLEM_IDS=" + selection + "\n")
    print("Browser problem selection: " + selection)


if __name__ == "__main__":
    main()
