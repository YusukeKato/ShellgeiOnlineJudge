import re
from typing import Annotated

from pydantic import AfterValidator, StringConstraints


MAX_PROBLEM_ID_CHARS = 64
PROBLEM_ID_PATTERN_TEXT = r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$"
PROBLEM_ID_PATTERN = re.compile(PROBLEM_ID_PATTERN_TEXT)


def validate_problem_id(problem_id: str) -> str:
    """Return a path-safe problem ID or raise ValueError."""
    if not 1 <= len(problem_id) <= MAX_PROBLEM_ID_CHARS:
        raise ValueError(
            f"problem_id must be between 1 and {MAX_PROBLEM_ID_CHARS} characters"
        )
    if not PROBLEM_ID_PATTERN.fullmatch(problem_id):
        raise ValueError("problem_id must contain only letters, numbers, and hyphens")
    return problem_id


ProblemId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=MAX_PROBLEM_ID_CHARS,
        pattern=PROBLEM_ID_PATTERN_TEXT,
    ),
    AfterValidator(validate_problem_id),
]
