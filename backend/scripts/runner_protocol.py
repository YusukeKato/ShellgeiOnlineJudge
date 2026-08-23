import os
import re

from pydantic import BaseModel, ConfigDict, Field

RUNNER_EXECUTE_PATH = "/internal/execute"
RUNNER_HEALTH_PATH = "/internal/health"
RUNNER_SHARED_SECRET_ENVIRONMENT = "RUNNER_SHARED_SECRET"
RUNNER_SHARED_SECRET_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
RUNNER_INSECURE_EXAMPLE_SECRET = "replace-with-at-least-32-random-characters"
MAX_RUNNER_OUTPUT_CHARS = 1_003
MAX_RUNNER_IMAGE_BASE64_CHARS = 1_000_000


class RunnerConfigurationError(RuntimeError):
    """Raised when the private runner channel is not configured safely."""


class RunnerExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: str = Field(max_length=MAX_RUNNER_OUTPUT_CHARS)
    image: str = Field(max_length=MAX_RUNNER_IMAGE_BASE64_CHARS)


def get_runner_shared_secret() -> str:
    secret = os.getenv(RUNNER_SHARED_SECRET_ENVIRONMENT, "")
    if (
        not RUNNER_SHARED_SECRET_PATTERN.fullmatch(secret)
        or secret == RUNNER_INSECURE_EXAMPLE_SECRET
    ):
        raise RunnerConfigurationError(
            f"{RUNNER_SHARED_SECRET_ENVIRONMENT} must contain 32 to 256 "
            "ASCII letters, digits, underscores, or hyphens"
        )
    return secret
