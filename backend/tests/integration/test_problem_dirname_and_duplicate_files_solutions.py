"""承認済みの親path抽出・内容別file分類をrootless sandboxと現行judgeで検査する。"""

import asyncio
import os
from pathlib import Path
import posixpath
import shlex
import uuid

import pytest

from soj_backend.judge import JudgeVerdict, ShellgeiJudge, TextJudgeInput, judge_text
from soj_runner.container_manager import ContainerManager
from soj_runner.run_shellgei import ShellgeiDockerClient
from soj_shared.models.execution import ExecutionStatus
from soj_shared.models.problem import TextJudgeSpecification
from soj_shared.problem_repository import build_problem_repository

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="解答の実行にはrootless Dockerへの明示指定が必要",
    ),
]
PROBLEMS = Path(__file__).resolve().parents[3] / "problems"
NORMAL = "STANDARD-00000071"
PRACTICE = "PRACTICE-dirname-01"
ALTERNATIVES = {
    NORMAL: 'mapfile -t files < <(sort input.txt); for a in "${files[@]}"; do group=(); for b in "${files[@]}"; do cmp -s -- "$a" "$b" && group+=("$b"); done; if [ "${#group[@]}" -gt 1 ] && [ "$a" = "${group[0]}" ]; then printf \'%s\' "${group[0]}"; printf \' | %s\' "${group[@]:1}"; printf \'\\n\'; fi; done',
    PRACTICE: """awk '{p=$0;if(p!~/\\//)p=".";else {sub(/\\/[^/]*$/,"",p);if(p=="")p="/"}print p}' input.txt""",
}
PATH_CASES = [
    ("empty", ""),
    ("bare", "file.txt\n"),
    ("root", "/file.txt\n"),
    ("deep_and_spaces", "deep/folder/file.txt\ndraft notes/my file.txt\n"),
    ("duplicates", "logs/a.txt\nlogs/b.txt\n"),
    ("leading_dot", "./docs/a.md\n../docs/b.md\n"),
    ("leading_hyphen_and_backslash", "-file.txt\nback\\slash/a.txt\n"),
    ("no_final_lf", "logs/a.txt\nbare.txt"),
]
FILE_CASES = [
    ("empty", "", {}),
    ("singleton", "data/a.txt\n", {"data/a.txt": "one\n"}),
    (
        "all_unique",
        "data/a.txt\ndata/b.txt\n",
        {"data/a.txt": "red\n", "data/b.txt": "blue\n"},
    ),
    (
        "all_equal",
        "data/z.txt\ndata/a.txt\ndata/b.txt\n",
        {"data/a.txt": "same\n", "data/b.txt": "same\n", "data/z.txt": "same\n"},
    ),
    (
        "empty_contents",
        "data/b.txt\ndata/a.txt\ndata/c.txt\n",
        {"data/a.txt": "", "data/b.txt": "", "data/c.txt": "x\n"},
    ),
    (
        "case_sensitive",
        "data/a.txt\ndata/b.txt\n",
        {"data/a.txt": "red\n", "data/b.txt": "RED\n"},
    ),
    (
        "spaces_and_no_final_input_lf",
        "data/with space.txt\ndata/copy.txt",
        {"data/with space.txt": "same\n", "data/copy.txt": "same\n"},
    ),
    (
        "content_final_lf",
        "data/a.txt\ndata/b.txt\ndata/c.txt\n",
        {"data/a.txt": "red", "data/b.txt": "red\n", "data/c.txt": "red"},
    ),
    (
        "group_order",
        "data/z.txt\ndata/c.txt\ndata/b.txt\ndata/a.txt\n",
        {
            "data/a.txt": "blue\n",
            "data/z.txt": "blue\n",
            "data/b.txt": "red\n",
            "data/c.txt": "red\n",
        },
    ),
]


def _expected(problem_id: str, fixture: str, files: dict[str, str]) -> str:
    """hash解法を使わず、親componentまたはfileの全内容から期待値を求める。"""
    if problem_id == PRACTICE:
        return "".join(
            (posixpath.dirname(p) or ".") + "\n" for p in fixture.splitlines()
        )
    groups: dict[str, list[str]] = {}
    for path in fixture.splitlines():
        groups.setdefault(files[path], []).append(path)
    return "".join(
        " | ".join(group) + "\n"
        for group in sorted(sorted(g) for g in groups.values() if len(g) > 1)
    )


@pytest.mark.parametrize("problem_id", (NORMAL, PRACTICE))
def test_dirname_and_duplicate_files_solutions_in_real_sandboxes(
    problem_id: str,
) -> None:
    """公開入力の参照解・別解・誤答と、pathや内容の境界を隔離した実行で照合する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(problem_id)
    manager = ContainerManager(
        pool_size=1, owner_id=f"soj-dirname-duplicates-{uuid.uuid4().hex}"
    )
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)
    reference = record.definition.reference_solution
    solutions = (reference, ALTERNATIVES[problem_id])

    def evaluate(
        label: str,
        command: str,
        expected: str,
        fixture: str | None = None,
        files: dict[str, str] | None = None,
        accepted: bool = True,
    ) -> None:
        """境界fixtureの作成もsandbox内に限定し、raw stdoutと現行judgeを照合する。"""
        setup = dict(files or {})
        if fixture is not None:
            setup["input.txt"] = fixture
        prefix = "".join(
            f"printf %s {shlex.quote(content)} > {shlex.quote(path)}; "
            for path, content in setup.items()
        )
        submitted = prefix + command
        assert len(submitted) <= 1000
        execution = asyncio.run(client.run_with_timeout(submitted, problem_id))
        context = (problem_id, label, execution)
        assert execution.status is ExecutionStatus.COMPLETED, context
        assert execution.exit_code == 0 and execution.stderr == "", context
        assert not execution.timed_out and not execution.truncated, context
        verdict = (
            judge.judge(execution, problem_id).verdict
            if fixture is None
            else judge_text(
                TextJudgeSpecification(type="text", expected_output=expected),
                record.definition.execution,
                TextJudgeInput(
                    stdout=execution.stdout,
                    stderr=execution.stderr,
                    exit_code=execution.exit_code,
                    timed_out=execution.timed_out,
                    truncated=execution.truncated,
                ),
            ).verdict
        )
        assert verdict is (
            JudgeVerdict.ACCEPTED if accepted else JudgeVerdict.WRONG_ANSWER
        ), context
        if accepted:
            assert execution.stdout == expected, context

    try:
        manager.initialize_pool()
        for index, solution in enumerate(solutions):
            evaluate(f"public-{index}", solution, record.expected_output)
        if problem_id == NORMAL:
            mistakes = [
                (
                    "include_unlisted",
                    reference.replace(
                        "xargs -r -d '\\n' sha256sum -- < input.txt",
                        "find data -type f -print0 | xargs -0 -r sha256sum --",
                    ),
                ),
                ("include_singletons", reference.replace("n>1", "n>0")),
                ("drop_paths", reference + " | sed 's|data/||g'"),
            ]
            cases = FILE_CASES
        else:
            mistakes = [
                (
                    "basename",
                    'while IFS= read -r p; do basename -- "$p"; done < input.txt',
                ),
                ("remove_duplicates", reference + " | sort -u"),
                (
                    "split_on_spaces",
                    'for p in $(cat input.txt); do dirname -- "$p"; done',
                ),
                ("missing_dot", "sed 's|/[^/]*$||' input.txt"),
            ]
            cases = [(label, fixture, {}) for label, fixture in PATH_CASES]
        for label, command in mistakes:
            evaluate(label, command, record.expected_output, accepted=False)
        for label, fixture, files in cases:
            expected = _expected(problem_id, fixture, files)
            for index, solution in enumerate(solutions):
                evaluate(f"{label}-{index}", solution, expected, fixture, files)
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
