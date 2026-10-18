"""問題だけの変更を識別し、共通UIと追加・変更問題の画面検査を選ぶ。"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
REPRESENTATIVES = ("PRACTICE-base64-01", "STANDARD-00000068")
# 全問題の画面検査を分けるCI job数。変更問題だけの検査は1 jobで行う。
FULL_REVIEW_SHARDS = 3
SHARD = re.compile(r"([0-9]+)/([1-9][0-9]*)")
# bundleや静的配信へ入り得るため、Markdownでも画面へ影響する可能性がある場所。
FRONTEND_ASSET_DIRS = ("frontend/src/", "frontend/public/")
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


def shard_ids(ids: list[str], shard: str) -> list[str]:
    """`k/n`形式で、ID順にn個へ均等に分けたk番目を返す。不正な指定は検査漏れを防ぐため失敗させる。"""
    match = SHARD.fullmatch(shard)
    if not match or int(match[1]) >= int(match[2]):
        raise ValueError("browser shard must be k/n with 0 <= k < n")
    return sorted(ids)[int(match[1]) :: int(match[2])]


def browser_plan(
    available: list[str], selection: str, shard: str = "0/1"
) -> tuple[list[str], list[str]]:
    """browser検査で開く(正規表現問題, 詳細検査問題)を返す。check.pyとtestの件数照合で共用する。

    全件modeでは全REGEX問題を正規表現の専用経路で、その他を詳細検査で確認し、両方をshardで分ける。
    変更問題だけのmodeは正規表現の代表1問と選択問題を1 jobで確認し、分割を受け付けない。
    """
    regex = sorted(pid for pid in available if pid.startswith("REGEX-"))
    selected = select_problem_ids(available, selection)
    if selection == "all":
        detail = [pid for pid in selected if not pid.startswith("REGEX-")]
        return shard_ids(regex, shard), shard_ids(detail, shard)
    if shard != "0/1":
        raise ValueError("only the full review is split into shards")
    return regex[:1], selected


def shards_for(selection: str) -> list[str]:
    """選択に応じたCI matrixのshard一覧を返す。全件だけを複数jobへ分ける。"""
    count = FULL_REVIEW_SHARDS if selection == "all" else 1
    return [f"{index}/{count}" for index in range(count)]


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
        elif path.endswith(".md") and not path.startswith(FRONTEND_ASSET_DIRS):
            # README・AGENTS.md等の文書は画面に出ない。frontendが取り込み得るdirは除く。
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
    """選択値とshard一覧をJSON一行ずつjob outputへ渡す。shellへevent本文やfile名を展開しない。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-output", action="store_true", required=True)
    parser.parse_args()
    selection = github_selection()
    shards = json.dumps(shards_for(selection))
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        output.write(f"browser_selection={selection}\nbrowser_shards={shards}\n")
    print("Browser problem selection: " + selection)
    print("Browser review shards: " + shards)


if __name__ == "__main__":
    main()
