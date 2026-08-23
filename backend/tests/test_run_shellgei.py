import asyncio
import base64
import io
import tarfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import scripts.run_shellgei as run_shellgei_module
from scripts.run_shellgei import (
    MAX_IMAGE_ARCHIVE_BYTES,
    MAX_IMAGE_BYTES,
    OUTPUT_IMAGE_SNAPSHOT_COMMAND,
    OUTPUT_IMAGE_SNAPSHOT_PATH,
    SandboxBusyError,
    ShellgeiDockerClient,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def image_archive(name: str, payload: bytes) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        info = tarfile.TarInfo(name)
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    return stream.getvalue()


class FakeContainer:
    def __init__(self, output: Any = None, image: bytes = b"image") -> None:
        self.id = "execution-container"
        self.output = [b"ok\n"] if output is None else output
        self.image = image
        self.killed = threading.Event()
        self.kill_calls = 0
        self.archive: bytes | None = None
        self.image_stream_read = False

    def put_archive(self, path: str, data: io.BytesIO) -> None:
        assert path == "/"
        self.archive = data.read()

    def exec_run(self, command: Any, **kwargs: Any) -> Any:
        if command == ["/bin/sh", "-c", OUTPUT_IMAGE_SNAPSHOT_COMMAND]:
            assert kwargs == {"stdout": False, "stderr": False}
            return SimpleNamespace(exit_code=0, output=None)
        if command.startswith("convert "):
            return SimpleNamespace(exit_code=0, output=b"")
        if command == "bash z.bash":
            return SimpleNamespace(exit_code=None, output=iter(self.output))
        raise AssertionError(f"unexpected command: {command}")

    def kill(self) -> None:
        self.kill_calls += 1
        self.killed.set()

    def get_archive(self, path: str) -> tuple[Any, dict[str, int]]:
        assert path == OUTPUT_IMAGE_SNAPSHOT_PATH
        assert self.killed.is_set()
        archive = image_archive(Path(path).name, self.image)
        return iter((archive,)), {"size": len(self.image)}


class FakeManager:
    def __init__(self, container: FakeContainer, pool_size: int = 1) -> None:
        self.container = container
        self.pool_size = pool_size
        self.released: list[FakeContainer] = []
        self.release_stopped_values: list[bool] = []

    def get_container(self) -> FakeContainer:
        return self.container

    def release_container(
        self, container: FakeContainer, already_stopped: bool = False
    ) -> None:
        self.released.append(container)
        self.release_stopped_values.append(already_stopped)


def make_client(container: FakeContainer) -> tuple[ShellgeiDockerClient, FakeManager]:
    manager = FakeManager(container)
    client = ShellgeiDockerClient(container_manager=manager, max_concurrent=1)
    client.base_dir = REPOSITORY_ROOT
    return client, manager


def test_normal_execution_stops_container_and_returns_bounded_results() -> None:
    container = FakeContainer(output=[b"hello\n"], image=b"jpeg-data")
    client, manager = make_client(container)

    output, image = client.exec_shellgei("printf hello", "STANDARD-00000001", 1, 1000)

    assert output == "hello\n"
    assert image == base64.b64encode(b"jpeg-data").decode("ascii")
    assert container.kill_calls == 1
    assert manager.released == [container]
    assert manager.release_stopped_values == [True]
    assert container.archive is not None
    with tarfile.open(fileobj=io.BytesIO(container.archive), mode="r:") as archive:
        command_file = archive.extractfile("z.bash")
        assert command_file is not None
        assert command_file.read() == b"printf hello"
    client.close()


def test_silent_execution_is_killed_at_deadline_and_worker_returns() -> None:
    container = FakeContainer()

    def silent_output() -> Any:
        container.killed.wait(timeout=2)
        if False:
            yield b""

    container.output = silent_output()
    client, manager = make_client(container)
    started = time.monotonic()

    output, image = client.exec_shellgei(
        "sleep infinity", "STANDARD-00000001", 0.05, 1000
    )

    assert time.monotonic() - started < 1
    assert output == "\n[Timed out]"
    assert image == ""
    assert container.kill_calls >= 1
    assert manager.released == [container]
    assert manager.release_stopped_values == [True]

    replacement = FakeContainer(output=[b"recovered"])
    manager.container = replacement
    recovered = client.executor.submit(
        client.exec_shellgei,
        "echo recovered",
        "STANDARD-00000001",
        1,
        1000,
    ).result(timeout=1)
    assert recovered[0] == "recovered"
    client.close()


def test_large_combined_stdout_stderr_is_bounded_and_kills_container() -> None:
    container = FakeContainer(output=[b"x" * 100_000])
    client, manager = make_client(container)

    output, image = client.exec_shellgei("yes", "STANDARD-00000001", 1, 10)

    assert output == "x" * 10 + "..."
    assert image == ""
    assert container.kill_calls >= 1
    assert manager.released == [container]
    client.close()


def test_oversized_image_is_rejected_before_stream_is_read() -> None:
    container = FakeContainer(output=[b"ok"])

    def oversized_archive(path: str) -> tuple[Any, dict[str, int]]:
        assert path == OUTPUT_IMAGE_SNAPSHOT_PATH

        def stream() -> Any:
            container.image_stream_read = True
            yield b"must not be read"

        return stream(), {"size": MAX_IMAGE_BYTES + 1}

    container.get_archive = oversized_archive  # type: ignore[method-assign]
    client, _ = make_client(container)

    output, image = client.exec_shellgei("echo ok", "STANDARD-00000001", 1, 1000)

    assert output == "ok"
    assert image == ""
    assert container.image_stream_read is False
    client.close()


def test_image_archive_transfer_is_bounded_even_with_false_size_metadata() -> None:
    container = FakeContainer(output=[b"ok"])

    def oversized_archive(path: str) -> tuple[Any, dict[str, int]]:
        assert path == OUTPUT_IMAGE_SNAPSHOT_PATH
        return iter((b"x" * (MAX_IMAGE_ARCHIVE_BYTES + 1),)), {"size": 1}

    container.get_archive = oversized_archive  # type: ignore[method-assign]
    client, _ = make_client(container)

    output, image = client.exec_shellgei("echo ok", "STANDARD-00000001", 1, 1000)

    assert output == "ok"
    assert image == ""
    client.close()


def test_setup_failure_is_cleaned_up_as_a_running_container() -> None:
    container = FakeContainer()

    def fail_put_archive(path: str, data: io.BytesIO) -> None:
        raise RuntimeError("archive upload failed")

    container.put_archive = fail_put_archive  # type: ignore[method-assign]
    client, manager = make_client(container)

    output, image = client.exec_shellgei("echo ok", "STANDARD-00000001", 1, 1000)

    assert output == "Error during execution: archive upload failed"
    assert image == ""
    assert manager.released == [container]
    assert manager.release_stopped_values == [False]
    client.close()


def test_hard_concurrency_limit_returns_busy_without_queueing() -> None:
    entered = threading.Event()
    finish = threading.Event()
    manager = FakeManager(FakeContainer())
    client = ShellgeiDockerClient(container_manager=manager, max_concurrent=1)

    def blocking_execution(*args: Any) -> list[str]:
        entered.set()
        finish.wait(timeout=2)
        return ["done", ""]

    client.exec_shellgei = blocking_execution  # type: ignore[assignment]

    async def scenario() -> None:
        first = asyncio.create_task(
            client.run_with_timeout("one", "problem", timeout=1)
        )
        while not entered.is_set():
            await asyncio.sleep(0.001)
        try:
            await client.run_with_timeout("two", "problem", timeout=1)
        except SandboxBusyError:
            pass
        else:
            raise AssertionError("SandboxBusyError was not raised")
        finish.set()
        assert await first == ["done", ""]

    asyncio.run(scenario())
    client.close()


def test_outer_timeout_keeps_capacity_reserved_until_worker_returns() -> None:
    entered = threading.Event()
    finish = threading.Event()
    manager = FakeManager(FakeContainer())
    client = ShellgeiDockerClient(container_manager=manager, max_concurrent=1)
    original_grace = run_shellgei_module.DOCKER_OPERATION_GRACE_SECONDS
    run_shellgei_module.DOCKER_OPERATION_GRACE_SECONDS = 0.05

    def blocking_execution(*args: Any) -> list[str]:
        entered.set()
        finish.wait(timeout=2)
        return ["done", ""]

    client.exec_shellgei = blocking_execution  # type: ignore[assignment]

    async def scenario() -> None:
        first = await client.run_with_timeout("one", "problem", timeout=0.01)
        assert first == ["Error: sandbox cleanup timed out.", ""]
        assert entered.is_set()

        try:
            await client.run_with_timeout("two", "problem", timeout=0.01)
        except SandboxBusyError:
            pass
        else:
            raise AssertionError(
                "capacity was released while the worker was still running"
            )

        finish.set()
        for _ in range(100):
            try:
                recovered = await client.run_with_timeout("three", "problem", timeout=1)
            except SandboxBusyError:
                await asyncio.sleep(0.001)
                continue
            assert recovered == ["done", ""]
            return
        raise AssertionError("capacity was not released after the worker returned")

    try:
        asyncio.run(scenario())
    finally:
        finish.set()
        run_shellgei_module.DOCKER_OPERATION_GRACE_SECONDS = original_grace
        client.close()
