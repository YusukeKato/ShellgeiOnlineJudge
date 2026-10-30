"""承認済みの見出し分割・段落整形を実sandboxと現行judgeで検査する。"""

import asyncio
import os
from pathlib import Path
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

ALTERNATIVES = {
    "PRACTICE-csplit-01": (
        'awk \'/^## / {if(n)printf "section%02d %d\\n",n-1,c; n++;c=0} {c++} END{if(n)printf "section%02d %d\\n",n-1,c}\' input.txt',
        'awk \'/^## /{f=sprintf("section%02d",n++)}{print > f}\' input.txt && for f in section[0-9][0-9]; do [ -f "$f" ] || continue; printf \'%s %s\\n\' "$f" "$(wc -l < "$f")"; done',
    ),
    "PRACTICE-fmt-01": (
        'awk \'NF{for(i=1;i<=NF;i++){printf "%s%s",sep,$i;sep=" "};next} {if(sep!="")print "";print "";sep=""} END{if(sep!="")print ""}\' input.txt',
    ),
}

BOUNDARIES = {
    "PRACTICE-csplit-01": [
        ("empty", ""),
        ("one_header", "## only\n"),
        ("one_section", "## only\na\nb\n"),
        ("adjacent_headers", "## a\n## b\n## c\n"),
        ("blank_body", "## a\n\n\n## b\nx\n"),
        ("inline_and_indented", "## a\ntext ## b\n ## c\n## d\ny\n"),
        ("duplicate_headers", "## same\nx\n## same\ny\nz\n"),
        ("japanese", "## a\n日本語\n\n## b\n青い空\n"),
        ("exact_marker", "## a\n##\n### other\n## b\n"),
        ("last_header_only", "## a\nx\n## b\n"),
    ],
    "PRACTICE-fmt-01": [
        ("empty", ""),
        ("one_word", "hello\n"),
        ("one_paragraph", "red\nblue\ngreen\n"),
        ("blank_only", "\n\n"),
        ("repeated_blanks", "red\n\n\nblue\n"),
        ("leading_and_trailing_blank", "\nred\nblue\n\n"),
        ("repeated_spaces", "red   blue\ngreen  yellow\n"),
        ("duplicates", "same words\n\nsame\nwords\n"),
        ("sentence_spacing", "First sentence.\nAnother   sentence.\n"),
        ("japanese", "赤い   花\n青い 空\n\n白い 雲\n"),
        ("tabs_between_words", "red\tblue\ngreen\tyellow\n"),
        ("no_final_lf", "red   blue\ngreen"),
    ],
}

MISTAKES = {
    "PRACTICE-csplit-01": [
        (
            "fixed_three_lines",
            'split -l 3 -d -a 2 input.txt section; for f in section[0-9][0-9]; do printf \'%s %s\\n\' "$f" "$(wc -l < "$f")"; done',
        ),
        (
            "unanchored",
            'csplit -s -z -f section input.txt \'/## /\' \'{*}\' && for f in section[0-9][0-9]; do [ -f "$f" ] || continue; printf \'%s %s\\n\' "$f" "$(wc -l < "$f")"; done',
        ),
        (
            "drop_blank_lines",
            "awk 'NF' input.txt > clean.txt; csplit -s -z -f section clean.txt '/^## /' '{*}' && for f in section[0-9][0-9]; do [ -f \"$f\" ] || continue; printf '%s %s\\n' \"$f\" \"$(wc -l < \"$f\")\"; done",
        ),
        (
            "without_header",
            'awk \'/^## /{if(n)printf "section%02d %d\\n",n-1,c; n++;c=0;next}{c++} END{printf "section%02d %d\\n",n-1,c}\' input.txt',
        ),
        (
            "one_based_labels",
            'awk \'/^## / {if(n)printf "section%02d %d\\n",n,c; n++;c=0} {c++} END{if(n)printf "section%02d %d\\n",n,c}\' input.txt',
        ),
        (
            "sort_lines",
            'sort input.txt > sorted.txt; csplit -s -z -f section sorted.txt \'/^## /\' \'{*}\' && for f in section[0-9][0-9]; do [ -f "$f" ] || continue; printf \'%s %s\\n\' "$f" "$(wc -l < "$f")"; done',
        ),
    ],
    "PRACTICE-fmt-01": [
        ("default_width", "fmt input.txt | tr -s ' '"),
        ("keep_spacing", "fmt -w 1000 input.txt"),
        ("merge_all", "paste -s -d ' ' input.txt | tr -s ' '"),
        ("keep_line_breaks", "tr -s ' ' < input.txt"),
        ("split_only", "fmt -s -w 1000 input.txt | tr -s ' '"),
        ("sort_paragraphs", "fmt -w 1000 input.txt | tr -s '[:blank:]' ' ' | sort -u"),
    ],
}


def _independent_expected(problem_id: str, fixture: str) -> str:
    """見出しの行位置と段落内の単語列を使い、shellの解法と独立に期待値を求める。"""
    if problem_id == "PRACTICE-csplit-01":
        lines = fixture.splitlines()
        starts = [i for i, line in enumerate(lines) if line.startswith("## ")]
        assert not lines or starts[0] == 0
        stops = starts[1:] + [len(lines)]
        return "".join(
            f"section{i:02d} {stop - start}\n"
            for i, (start, stop) in enumerate(zip(starts, stops))
        )
    output: list[str] = []
    paragraph: list[str] = []
    for line in fixture.splitlines():
        if line:
            paragraph.extend(line.split())
        else:
            if paragraph:
                output.append(" ".join(paragraph) + "\n")
                paragraph = []
            output.append("\n")
    if paragraph:
        output.append(" ".join(paragraph) + "\n")
    return "".join(output)


@pytest.mark.parametrize("problem_id", tuple(ALTERNATIVES))
def test_csplit_and_fmt_solutions_in_real_sandboxes(problem_id: str) -> None:
    """公開入力の参照解・自然な別解・誤答と、見出しや段落の境界入力を検査する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(problem_id)
    manager = ContainerManager(
        pool_size=1, owner_id=f"soj-csplit-fmt-{uuid.uuid4().hex}"
    )
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)
    solutions = (record.definition.reference_solution, *ALTERNATIVES[problem_id])

    def evaluate(
        label: str,
        fixture: str | None,
        command: str,
        expected: str,
        accepted: bool = True,
    ) -> None:
        """公開入力またはsandbox内の試験入力を実行し、raw出力と実judgeの両方を照合する。"""
        submitted = (
            command
            if fixture is None
            else f"printf %s {shlex.quote(fixture)} > input.txt; {command}"
        )
        assert len(submitted) <= 1000
        execution = asyncio.run(client.run_with_timeout(submitted, problem_id))
        context = (problem_id, label, execution)
        assert execution.status is ExecutionStatus.COMPLETED, context
        assert execution.exit_code == 0 and execution.stderr == "", context
        assert not execution.timed_out and not execution.truncated, context
        if fixture is None:
            verdict = judge.judge(execution, problem_id).verdict
        else:
            verdict = judge_text(
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
        assert verdict is (
            JudgeVerdict.ACCEPTED if accepted else JudgeVerdict.WRONG_ANSWER
        ), context
        if accepted:
            assert execution.stdout == expected, context

    try:
        manager.initialize_pool()
        for index, solution in enumerate(solutions):
            evaluate(f"public-{index}", None, solution, record.expected_output)
        for label, command in MISTAKES[problem_id]:
            evaluate(label, None, command, record.expected_output, False)
        for label, fixture in BOUNDARIES[problem_id]:
            expected = _independent_expected(problem_id, fixture)
            for index, solution in enumerate(solutions):
                evaluate(f"{label}-{index}", fixture, solution, expected)
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
