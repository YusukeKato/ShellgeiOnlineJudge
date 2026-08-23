import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi import HTTPException

import runner_main
from models.model_shellgei import ShellgeiData
from scripts.admission_control import (
    DEFAULT_SANDBOX_START_BURST,
    DEFAULT_SANDBOX_START_RATE_PER_SECOND,
    SandboxStartRateLimiter,
)


def test_start_rate_limiter_defaults_match_the_production_policy() -> None:
    limiter = SandboxStartRateLimiter()

    assert limiter.rate_per_second == DEFAULT_SANDBOX_START_RATE_PER_SECOND == 1.0
    assert limiter.burst == DEFAULT_SANDBOX_START_BURST == 3


def test_start_rate_limiter_allows_burst_then_refills_at_fixed_rate() -> None:
    now = [100.0]
    limiter = SandboxStartRateLimiter(
        rate_per_second=1.0,
        burst=3,
        clock=lambda: now[0],
    )

    assert [limiter.try_acquire() for _ in range(4)] == [True, True, True, False]

    now[0] += 0.999
    assert limiter.try_acquire() is False

    now[0] += 0.001
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False


def test_start_rate_limiter_never_refills_beyond_burst_capacity() -> None:
    now = [0.0]
    limiter = SandboxStartRateLimiter(
        rate_per_second=1.0,
        burst=3,
        clock=lambda: now[0],
    )

    assert limiter.try_acquire() is True
    now[0] = 100.0

    assert [limiter.try_acquire() for _ in range(4)] == [True, True, True, False]


def test_start_rate_limiter_is_atomic_for_concurrent_requests() -> None:
    limiter = SandboxStartRateLimiter(
        rate_per_second=1.0,
        burst=3,
        clock=lambda: 0.0,
    )

    with ThreadPoolExecutor(max_workers=16) as executor:
        admitted = list(executor.map(lambda _request: limiter.try_acquire(), range(64)))

    assert admitted.count(True) == 3
    assert admitted.count(False) == 61


@pytest.mark.parametrize(
    ("rate_per_second", "burst"),
    [(0.0, 1), (-1.0, 1), (float("inf"), 1), (float("nan"), 1), (1.0, 0)],
)
def test_start_rate_limiter_rejects_invalid_configuration(
    rate_per_second: float,
    burst: int,
) -> None:
    with pytest.raises(ValueError):
        SandboxStartRateLimiter(rate_per_second=rate_per_second, burst=burst)


def test_runner_rejects_rate_limited_request_before_docker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class RejectAllStarts:
        def try_acquire(self) -> bool:
            return False

    async def unexpected_execution(*_args: object) -> list[str]:
        raise AssertionError("Docker execution must not start")

    monkeypatch.setattr(
        runner_main,
        "sandbox_start_rate_limiter",
        RejectAllStarts(),
    )
    monkeypatch.setattr(
        runner_main.docker_client,
        "run_with_timeout",
        unexpected_execution,
    )
    yaml_dir = tmp_path / "problems" / "yaml_data"
    yaml_dir.mkdir(parents=True)
    (yaml_dir / "STANDARD-00000001.yaml").touch()
    monkeypatch.setattr(
        runner_main,
        "__file__",
        str(tmp_path / "runner_main.py"),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            runner_main.execute_shellgei(
                ShellgeiData(
                    shellgei="printf test",
                    problem_id="STANDARD-00000001",
                )
            )
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == "Runner is busy"
