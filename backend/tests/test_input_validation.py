import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError

from api.api_shellgei import post_shellgei
from main import app
from models.model_shellgei import MAX_SHELLGEI_CHARS, ShellgeiData
from scripts.input_validation import MAX_PROBLEM_ID_CHARS, ProblemId
from scripts.judge import ShellgeiJudge
from scripts.run_shellgei import ShellgeiDockerClient


PROBLEMS_DIR = Path(__file__).resolve().parents[2] / "problems" / "yaml_data"
PROBLEM_ID_ADAPTER = TypeAdapter(ProblemId)


INVALID_PROBLEM_IDS = [
    "../STANDARD-00000001",
    "STANDARD-00000001/../../etc/passwd",
    r"STANDARD-00000001\..\secret",
    ".",
    "STANDARD_00000001",
    "-STANDARD-00000001",
    "STANDARD-00000001-",
    "STANDARD--00000001",
    "STANDARD-00000001\n",
    "ＳＴＡＮＤＡＲＤ-00000001",
    "STANDARD%2F00000001",
    "A" * (MAX_PROBLEM_ID_CHARS + 1),
]


@pytest.mark.parametrize("problem_id", INVALID_PROBLEM_IDS)
def test_problem_id_rejects_non_path_safe_values(problem_id: str) -> None:
    with pytest.raises(ValidationError):
        PROBLEM_ID_ADAPTER.validate_python(problem_id)


def test_all_existing_problem_ids_pass_validation() -> None:
    yaml_paths = sorted(PROBLEMS_DIR.glob("*.yaml"))

    assert yaml_paths
    for yaml_path in yaml_paths:
        assert PROBLEM_ID_ADAPTER.validate_python(yaml_path.stem) == yaml_path.stem


def test_openapi_schema_exposes_input_constraints() -> None:
    schema = app.openapi()
    problem_parameter = schema["paths"]["/api/problems/{problem_id}"]["get"][
        "parameters"
    ][0]["schema"]
    body_schema = schema["components"]["schemas"]["ShellgeiData"]

    assert problem_parameter["minLength"] == 1
    assert problem_parameter["maxLength"] == MAX_PROBLEM_ID_CHARS
    assert problem_parameter["pattern"]
    assert body_schema["properties"]["shellgei"]["maxLength"] == MAX_SHELLGEI_CHARS
    assert body_schema["additionalProperties"] is False


def test_shellgei_data_normalizes_carriage_returns() -> None:
    data = ShellgeiData(
        shellgei="printf 'first\r\nsecond'\r",
        problem_id="STANDARD-00000001",
    )

    assert data.shellgei == "printf 'first\nsecond'"


@pytest.mark.parametrize(
    "shellgei",
    [
        "",
        "x" * (MAX_SHELLGEI_CHARS + 1),
        "printf '\x00'",
        "\ud800",
    ],
)
def test_shellgei_data_rejects_invalid_commands(shellgei: str) -> None:
    with pytest.raises(ValidationError):
        ShellgeiData(shellgei=shellgei, problem_id="STANDARD-00000001")


def test_shellgei_data_accepts_the_frontend_character_limit() -> None:
    shellgei = "あ" * MAX_SHELLGEI_CHARS

    data = ShellgeiData(shellgei=shellgei, problem_id="STANDARD-00000001")

    assert data.shellgei == shellgei


def test_shellgei_data_rejects_extra_json_fields() -> None:
    with pytest.raises(ValidationError):
        ShellgeiData.model_validate(
            {
                "shellgei": "true",
                "problem_id": "STANDARD-00000001",
                "image": "unexpected",
            }
        )


def test_unknown_problem_is_rejected_before_database_or_sandbox_work() -> None:
    data = ShellgeiData(shellgei="true", problem_id="MISSING-00000001")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(post_shellgei(data))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Problem not found"


class _UnusedContainerManager:
    pool_size = 1

    def get_container(self) -> Any:
        raise AssertionError("invalid problem IDs must not lease a container")


@pytest.mark.parametrize("problem_id", ["../secret", "A" * 65])
def test_executor_rejects_invalid_problem_id_before_leasing_container(
    problem_id: str,
) -> None:
    client = ShellgeiDockerClient(
        container_manager=_UnusedContainerManager(),
        max_concurrent=1,
    )
    try:
        assert client.exec_shellgei("true", problem_id, 1, 1000) == [
            "Error: invalid problem ID.",
            "",
        ]
    finally:
        client.close()


def test_judge_rejects_invalid_problem_id_before_reading_files() -> None:
    judge = ShellgeiJudge()

    assert judge.judge("output", "", "../secret") == "Error: invalid problem ID."
