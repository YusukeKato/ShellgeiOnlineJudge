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
from scripts.container_manager import SANDBOX_WORK_DIRECTORY
from scripts.run_shellgei import (
    EXECUTION_ARCHIVE_ENVIRONMENT,
    EXECUTION_ARCHIVE_EXTRACT_COMMAND,
    MAX_IMAGE_BYTES,
    SandboxBusyError,
    ShellgeiDockerClient,
)
from scripts.problem_repository import build_problem_repository


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROBLEM_REPOSITORY = build_problem_repository(
    REPOSITORY_ROOT / "problems/v3",
    REPOSITORY_ROOT / "problems/image",
    REPOSITORY_ROOT / "problems/v3/manifest.json",
)


class FakeContainer:
    def __init__(self, output: Any = None, image: bytes = b"image") -> None:
        """模擬command出力と画像を受け取り、観測可能なcontainer状態を初期化する。"""
        self.id = "execution-container"
        self.output = [b"ok\n"] if output is None else output
        self.image = image
        self.killed = threading.Event()
        self.kill_calls = 0
        self.archive: bytes | None = None
        self.setup_error: Exception | None = None
        self.commands: list[Any] = []

    def exec_run(self, command: Any, **kwargs: Any) -> Any:
        """入力commandに応じてarchive展開・実行・画像取得の模擬結果を返す。"""
        self.commands.append(command)
        if command == ["/bin/sh", "-c", EXECUTION_ARCHIVE_EXTRACT_COMMAND]:
            if self.setup_error is not None:
                raise self.setup_error
            encoded_archive = kwargs.pop("environment")[EXECUTION_ARCHIVE_ENVIRONMENT]
            assert kwargs == {
                "stdout": False,
                "stderr": True,
                "workdir": SANDBOX_WORK_DIRECTORY,
            }
            self.archive = base64.b64decode(encoded_archive, validate=True)
            return SimpleNamespace(exit_code=0, output=None)
        if command == [
            "/usr/bin/head",
            "-c",
            str(MAX_IMAGE_BYTES + 1),
            "--",
            "/work/media/output.jpg",
        ]:
            assert kwargs == {"stdout": True, "stderr": False, "stream": True}
            assert not self.killed.is_set()
            return SimpleNamespace(exit_code=None, output=iter((self.image,)))
        if command == ["bash", "z.bash"]:
            assert kwargs == {
                "demux": False,
                "stream": True,
                "workdir": SANDBOX_WORK_DIRECTORY,
            }
            return SimpleNamespace(exit_code=None, output=iter(self.output))
        raise AssertionError(f"unexpected command: {command}")

    def kill(self) -> None:
        """kill回数を加算し、container停止eventを設定する。"""
        self.kill_calls += 1
        self.killed.set()


class FakeManager:
    def __init__(self, container: FakeContainer, pool_size: int = 1) -> None:
        """貸出対象containerとpool数を受け取り、release観測用listを初期化する。"""
        self.container = container
        self.pool_size = pool_size
        self.released: list[FakeContainer] = []
        self.release_stopped_values: list[bool] = []

    def get_container(self) -> FakeContainer:
        """現在poolへ設定されている模擬containerを返す。"""
        return self.container

    def release_container(
        self, container: FakeContainer, already_stopped: bool = False
    ) -> None:
        """返却containerと停止済みflagを入力として受け取り、観測用listへ記録する。"""
        self.released.append(container)
        self.release_stopped_values.append(already_stopped)


def make_client(container: FakeContainer) -> tuple[ShellgeiDockerClient, FakeManager]:
    # fake containerと実問題repositoryを注入したclient、および観測用managerを返す。
    manager = FakeManager(container)
    client = ShellgeiDockerClient(
        container_manager=manager,
        max_concurrent=1,
        problem_repository=PROBLEM_REPOSITORY,
    )
    return client, manager


def test_normal_execution_stops_container_and_returns_bounded_results() -> None:
    # 正常実行でcommand・画像を返し、containerを停止済みとして返却することを確認する。
    container = FakeContainer(output=[b"hello\n"], image=b"jpeg-data")
    client, manager = make_client(container)

    output, image = client.exec_shellgei("printf hello", "STANDARD-00000001", 1, 1000)

    assert output == "hello\n"
    assert image == ""
    assert not any(command[0] == "/usr/bin/head" for command in container.commands)
    assert container.kill_calls == 1
    assert manager.released == [container]
    assert manager.release_stopped_values == [True]
    assert container.archive is not None
    with tarfile.open(fileobj=io.BytesIO(container.archive), mode="r:") as archive:
        command_file = archive.extractfile("z.bash")
        assert command_file is not None
        assert command_file.read() == b"printf hello"
    client.close()


def test_empty_successful_output_is_not_replaced_with_null_literal() -> None:
    # 正常な空出力をliteral NULLへ置換せず、空文字列のまま返すことを確認する。
    container = FakeContainer(output=[])
    client, _ = make_client(container)

    output, _ = client.exec_shellgei("true", "STANDARD-00000001", 1, 1000)

    assert output == ""
    client.close()


def test_image_problem_captures_only_the_schema_artifact_path() -> None:
    # 画像問題ではschema指定pathだけを上限付きで読み、Base64 artifactを返すことを確認する。
    payload = b"\xff\xd8image\xff\xd9"
    container = FakeContainer(output=[], image=payload)
    client, _ = make_client(container)

    _, artifact = client.exec_shellgei("true", "IMAGE-00000001", 1, 1000)

    assert artifact == base64.b64encode(payload).decode("ascii")
    assert [
        "/usr/bin/head",
        "-c",
        str(MAX_IMAGE_BYTES + 1),
        "--",
        "/work/media/output.jpg",
    ] in container.commands
    client.close()


def test_silent_execution_is_killed_at_deadline_and_worker_returns() -> None:
    # 無出力commandを期限でkillし、同じworkerが後続requestを処理できることを確認する。
    container = FakeContainer()

    def silent_output() -> Any:
        """container停止までbyteを生成せず待機する模擬streamを返すgenerator。"""
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
    # 出力上限超過時に表示を切り詰め、実行containerをkillすることを確認する。
    container = FakeContainer(output=[b"x" * 100_000])
    client, manager = make_client(container)

    output, image = client.exec_shellgei("yes", "STANDARD-00000001", 1, 10)

    assert output == "x" * 10 + "..."
    assert image == ""
    assert container.kill_calls >= 1
    assert manager.released == [container]
    client.close()


def test_oversized_image_is_rejected() -> None:
    # 許容byte数を超える画像を空文字列へ変換し、text結果は保持することを確認する。
    container = FakeContainer(output=[b"ok"], image=b"x" * (MAX_IMAGE_BYTES + 1))
    client, _ = make_client(container)

    output, image = client.exec_shellgei("echo ok", "IMAGE-00000001", 1, 1000)

    assert output == "ok"
    assert image == ""
    client.close()


def test_image_stream_is_bounded_before_base64_encoding() -> None:
    # 画像streamを全量保持せずbyte上限で拒否してからbase64処理を止めることを確認する。
    container = FakeContainer(output=[b"ok"], image=b"x" * (MAX_IMAGE_BYTES + 65_536))
    client, _ = make_client(container)

    output, image = client.exec_shellgei("echo ok", "IMAGE-00000001", 1, 1000)

    assert output == "ok"
    assert image == ""
    client.close()


def test_setup_failure_is_cleaned_up_as_a_running_container() -> None:
    # sandbox file準備失敗をerror結果へ変換し、未停止containerとして返却することを確認する。
    container = FakeContainer()
    container.setup_error = RuntimeError("archive transfer failed")
    client, manager = make_client(container)

    output, image = client.exec_shellgei("echo ok", "STANDARD-00000001", 1, 1000)

    assert output == "Error during execution: archive transfer failed"
    assert image == ""
    assert manager.released == [container]
    assert manager.release_stopped_values == [False]
    client.close()


def test_hard_concurrency_limit_returns_busy_without_queueing() -> None:
    # 実行slot使用中の追加requestをqueueへ入れずSandboxBusyErrorにすることを確認する。
    entered = threading.Event()
    finish = threading.Event()
    manager = FakeManager(FakeContainer())
    client = ShellgeiDockerClient(container_manager=manager, max_concurrent=1)

    def blocking_execution(*args: Any) -> list[str]:
        """入力を使用せずrelease通知まで待機し、固定実行結果を返す。"""
        entered.set()
        finish.wait(timeout=2)
        return ["done", ""]

    client.exec_shellgei = blocking_execution  # type: ignore[assignment]

    async def scenario() -> None:
        """1枠を占有した状態で2件目を送り、即時busyになる非同期手順を実行する。"""
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
    # 外側timeout後もthread終了までslotを保持し、終了後に再利用できることを確認する。
    entered = threading.Event()
    finish = threading.Event()
    manager = FakeManager(FakeContainer())
    client = ShellgeiDockerClient(container_manager=manager, max_concurrent=1)
    original_grace = run_shellgei_module.DOCKER_OPERATION_GRACE_SECONDS
    run_shellgei_module.DOCKER_OPERATION_GRACE_SECONDS = 0.05

    def blocking_execution(*args: Any) -> list[str]:
        """入力を使用せずrelease通知まで同期処理を継続し、固定結果を返す。"""
        entered.set()
        finish.wait(timeout=2)
        return ["done", ""]

    client.exec_shellgei = blocking_execution  # type: ignore[assignment]

    async def scenario() -> None:
        """外側timeout、busy継続、worker終了後のslot回復を順番に検証する。"""
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
