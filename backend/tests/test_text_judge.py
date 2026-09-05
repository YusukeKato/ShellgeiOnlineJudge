import pytest
from pydantic import ValidationError

from soj_shared.models.problem import (
    ExecutionSpecification,
    ExitCodePolicy,
    StderrPolicy,
    TextJudgeSpecification,
)
from soj_backend.judge import (
    JudgeReason,
    JudgeResult,
    JudgeVerdict,
    TextJudgeInput,
    judge_text,
)


def _execution_specification(
    *,
    exit_code: ExitCodePolicy = "ignore",
    stderr: StderrPolicy = "merge",
) -> ExecutionSpecification:
    # 任意の終了code・stderr policyを持つ、fixtureなしの実行仕様を返す。
    return ExecutionSpecification(
        stdin="",
        fixtures=(),
        exit_code=exit_code,
        stderr=stderr,
    )


def _judge(
    expected: str,
    execution: TextJudgeInput,
    *,
    exit_code: ExitCodePolicy = "ignore",
    stderr: StderrPolicy = "merge",
) -> JudgeResult:
    # 期待出力・policy・実行結果を純粋text judgeへ渡し、型付き結果を返す。
    return judge_text(
        TextJudgeSpecification(type="text", expected_output=expected),
        _execution_specification(exit_code=exit_code, stderr=stderr),
        execution,
    )


@pytest.mark.parametrize(
    "actual,expected,accepted",
    [
        ("same", "same", True),
        ("same\n", "same", True),
        ("same ", "same\n", True),
        ("same\r\n", "same", True),
        ("same\t", "same", False),
        ("a b", "a  b", False),
        ("a\nb", "a b", False),
        ("", "", True),
        ("NULL", "", False),
        ("SPACE", " ", False),
        ("NEWLINE", "\n", False),
        ("LT", "<", False),
        ("GT", ">", False),
    ],
)
def test_text_judge_whitespace_and_literal_truth_table(
    actual: str,
    expected: str,
    accepted: bool,
) -> None:
    # 空白規則と旧置換tokenのliteral衝突が、明示した期待結果になることを確認する。
    result = _judge(expected, TextJudgeInput(stdout=actual))

    assert (result.verdict is JudgeVerdict.ACCEPTED) is accepted


@pytest.mark.parametrize("exit_code", [1, 127, -1])
def test_text_judge_requires_zero_exit_code_when_configured(exit_code: int) -> None:
    # zero policyで非0終了codeを受け取ると、出力一致でも実行失敗になることを確認する。
    result = _judge(
        "same",
        TextJudgeInput(stdout="same", exit_code=exit_code),
        exit_code="zero",
    )

    assert result == JudgeResult(
        verdict=JudgeVerdict.EXECUTION_FAILURE,
        reason=JudgeReason.NON_ZERO_EXIT,
    )


def test_text_judge_can_ignore_non_zero_exit_code() -> None:
    # ignore policyでは非0終了codeでもstdout一致を判定できることを確認する。
    result = _judge("same", TextJudgeInput(stdout="same", exit_code=1))

    assert result.verdict is JudgeVerdict.ACCEPTED


@pytest.mark.parametrize(
    "stderr_policy,expected,accepted",
    [
        ("merge", "outerror", True),
        ("ignore", "out", True),
        ("must_be_empty", "out", False),
    ],
)
def test_text_judge_applies_stderr_policy(
    stderr_policy: StderrPolicy,
    expected: str,
    accepted: bool,
) -> None:
    # stderrの結合・無視・空必須policyが、それぞれ明示した判定になることを確認する。
    result = _judge(
        expected,
        TextJudgeInput(stdout="out", stderr="error"),
        stderr=stderr_policy,
    )

    assert (result.verdict is JudgeVerdict.ACCEPTED) is accepted
    if stderr_policy == "must_be_empty":
        assert result.reason is JudgeReason.STDERR_NOT_EMPTY


@pytest.mark.parametrize(
    "execution,reason",
    [
        (TextJudgeInput(stdout="same", timed_out=True), JudgeReason.TIMED_OUT),
        (
            TextJudgeInput(stdout="same", truncated=True),
            JudgeReason.OUTPUT_TRUNCATED,
        ),
    ],
)
def test_text_judge_rejects_incomplete_execution_output(
    execution: TextJudgeInput,
    reason: JudgeReason,
) -> None:
    # timeoutまたは切り詰め済み出力を、文字列一致だけで正解にしないことを確認する。
    result = _judge("same", execution)

    assert result == JudgeResult(
        verdict=JudgeVerdict.EXECUTION_FAILURE,
        reason=reason,
    )


def test_judge_models_are_strict_and_immutable() -> None:
    # 判定input/resultが代入変更と型の暗黙変換を拒否することを確認する。
    execution = TextJudgeInput(stdout="same")
    result = JudgeResult(verdict=JudgeVerdict.ACCEPTED)

    with pytest.raises(ValidationError):
        execution.stdout = "changed"
    with pytest.raises(ValidationError):
        result.verdict = JudgeVerdict.WRONG_ANSWER
    with pytest.raises(ValidationError):
        TextJudgeInput(stdout="same", exit_code="0")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "verdict,legacy_code",
    [
        (JudgeVerdict.ACCEPTED, "1"),
        (JudgeVerdict.WRONG_IMAGE, "2"),
        (JudgeVerdict.WRONG_ANSWER, "3"),
        (JudgeVerdict.WRONG_TEXT_AND_IMAGE, "4"),
        (JudgeVerdict.EXECUTION_FAILURE, "4"),
        (JudgeVerdict.JUDGE_ERROR, "4"),
    ],
)
def test_typed_verdict_maps_to_existing_public_code(
    verdict: JudgeVerdict,
    legacy_code: str,
) -> None:
    # 各typed verdictが互換public APIの数字codeへ決定的に変換されることを確認する。
    assert JudgeResult(verdict=verdict).legacy_code() == legacy_code
