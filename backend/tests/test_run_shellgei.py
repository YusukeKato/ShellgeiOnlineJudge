import asyncio
import base64
import io
import tarfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import soj_runner.run_shellgei as run_shellgei_module
from soj_shared.models.execution import ExecutionResult, ExecutionStatus
from soj_runner.container_manager import SANDBOX_WORK_DIRECTORY
from soj_runner.run_shellgei import (
    MAX_IMAGE_BYTES,
    SandboxBusyError,
    ShellgeiDockerClient,
)
from soj_shared.problem_repository import build_problem_repository
from soj_runner.sandbox_executor import (
    EXECUTION_ARCHIVE_ENVIRONMENT,
    EXECUTION_ARCHIVE_EXTRACT_COMMAND,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROBLEM_REPOSITORY = build_problem_repository(
    REPOSITORY_ROOT / "problems/v3",
    REPOSITORY_ROOT / "problems/image",
    REPOSITORY_ROOT / "problems/v3/manifest.json",
)


def completed_result(stdout: str = "done") -> ExecutionResult:
    # 任意stdoutから、非同期slotテスト用の正常な構造化結果を返す。
    return ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        stdout=stdout,
        stderr="",
        exit_code=0,
        timed_out=False,
        truncated=False,
        duration_ms=1,
        artifact=None,
        error=None,
    )


class FakeDockerApi:
    def __init__(self, container: "FakeContainer") -> None:
        """親containerを受け取り、低レベルDocker exec呼出しの模擬APIを初期化する。"""
        self.container = container

    def exec_create(
        self, container_id: str, command: Any, **kwargs: Any
    ) -> dict[str, str]:
        """exec作成引数を検証・記録し、固定exec IDまたは設定済み例外を返す。"""
        assert container_id == self.container.id
        assert command == ["bash", "z.bash"]
        assert kwargs == {
            "stdout": True,
            "stderr": True,
            "stdin": False,
            "tty": False,
            "workdir": SANDBOX_WORK_DIRECTORY,
        }
        self.container.commands.append(command)
        if self.container.execution_error is not None:
            raise self.container.execution_error
        return {"Id": "exec-1"}

    def exec_start(self, exec_id: str, **kwargs: Any) -> Any:
        """固定exec IDのstdout/stderrをdemux tuple列として遅延返却する。"""
        assert exec_id == "exec-1"
        assert kwargs == {"stream": True, "demux": True}

        def chunks() -> Any:
            """設定済みstdoutとstderrをDocker demux形式で順に生成する。"""
            stdout_chunks = (
                (self.container.output,)
                if isinstance(self.container.output, bytes)
                else self.container.output
            )
            for chunk in stdout_chunks:
                if isinstance(chunk, tuple):
                    yield chunk
                else:
                    yield chunk, None
            stderr_chunks = (
                (self.container.stderr,)
                if isinstance(self.container.stderr, bytes)
                else self.container.stderr
            )
            for chunk in stderr_chunks:
                yield None, chunk

        return chunks()

    def exec_inspect(self, exec_id: str) -> dict[str, int | None]:
        """固定exec IDを検証し、設定済み終了codeを返す。"""
        assert exec_id == "exec-1"
        if self.container.inspect_error is not None:
            raise self.container.inspect_error
        return {"ExitCode": self.container.exit_code}


class FakeContainer:
    def __init__(
        self,
        output: Any = None,
        image: bytes = b"image",
        stderr: Any = None,
        exit_code: int | None = 0,
    ) -> None:
        """模擬command出力と画像を受け取り、観測可能なcontainer状態を初期化する。"""
        self.id = "execution-container"
        self.output = [b"ok\n"] if output is None else output
        self.stderr = [] if stderr is None else stderr
        self.exit_code = exit_code
        self.image = image
        self.killed = threading.Event()
        self.kill_calls = 0
        self.archive: bytes | None = None
        self.setup_error: Exception | None = None
        self.setup_exit_code = 0
        self.execution_error: Exception | None = None
        self.inspect_error: Exception | None = None
        self.artifact_error: Exception | None = None
        self.kill_error: Exception | None = None
        self.kill_started = threading.Event()
        self.allow_kill: threading.Event | None = None
        self.commands: list[Any] = []
        self.client = SimpleNamespace(api=FakeDockerApi(self))

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
            return SimpleNamespace(exit_code=self.setup_exit_code, output=None)
        if command == [
            "/usr/bin/head",
            "-c",
            str(MAX_IMAGE_BYTES + 1),
            "--",
            "/work/media/output.jpg",
        ]:
            assert kwargs == {"stdout": True, "stderr": False, "stream": True}
            assert not self.killed.is_set()
            if self.artifact_error is not None:
                raise self.artifact_error
            return SimpleNamespace(exit_code=None, output=iter((self.image,)))
        raise AssertionError(f"unexpected command: {command}")

    def kill(self) -> None:
        """kill回数を加算し、container停止eventを設定する。"""
        self.kill_calls += 1
        self.kill_started.set()
        if self.allow_kill is not None:
            self.allow_kill.wait(timeout=2)
        if self.kill_error is not None:
            raise self.kill_error
        self.killed.set()


class FakeManager:
    def __init__(self, container: FakeContainer, pool_size: int = 1) -> None:
        """貸出対象containerとpool数を受け取り、release観測用listを初期化する。"""
        self.container = container
        self.pool_size = pool_size
        self.released: list[FakeContainer] = []
        self.release_stopped_values: list[bool] = []
        self.get_error: Exception | None = None

    def get_container(self) -> FakeContainer:
        """現在poolへ設定されている模擬containerを返す。"""
        if self.get_error is not None:
            raise self.get_error
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
    # 正常実行で構造化出力を返し、containerを停止済みとして返却することを確認する。
    container = FakeContainer(output=[b"hello\n"], image=b"jpeg-data")
    client, manager = make_client(container)

    result = client.exec_shellgei("printf hello", "STANDARD-00000001", 1, 1000)

    assert result.status is ExecutionStatus.COMPLETED
    assert result.stdout == "hello\n"
    assert result.stderr == ""
    assert result.exit_code == 0
    assert result.duration_ms >= 0
    assert result.artifact is None
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


def test_execution_separates_stdout_stderr_exit_code_and_preserves_nul() -> None:
    # stdout/stderr、非0終了codeを分離し、不正UTF-8だけを除いてNULを保持する。
    container = FakeContainer(
        output=[b"out\xff\x00"],
        stderr=[b"error"],
        exit_code=7,
    )
    client, _ = make_client(container)

    result = client.exec_shellgei("command", "STANDARD-00000001", 1, 1000)

    assert result.status is ExecutionStatus.COMPLETED
    assert result.stdout == "out\x00"
    assert result.stderr == "error"
    assert result.exit_code == 7
    assert result.legacy_output() == "out\x00error"
    client.close()


def test_character_limit_truncates_ascii_before_protocol_conversion() -> None:
    # byte上限未満でも文字数上限を超えるASCII出力を切り詰めとして記録する。
    container = FakeContainer(output=[b"x" * 11])
    client, _ = make_client(container)

    result = client.exec_shellgei("printf", "STANDARD-00000001", 1, 10)

    assert result.status is ExecutionStatus.OUTPUT_LIMIT
    assert result.stdout == "x" * 10
    assert result.truncated is True
    client.close()


def test_empty_successful_output_is_not_replaced_with_null_literal() -> None:
    # 正常な空出力をliteral NULLへ置換せず、空文字列のまま返すことを確認する。
    container = FakeContainer(output=[])
    client, _ = make_client(container)

    result = client.exec_shellgei("true", "STANDARD-00000001", 1, 1000)

    assert result.stdout == ""
    assert result.legacy_output() == ""
    client.close()


def test_image_problem_captures_only_the_schema_artifact_path() -> None:
    # 画像問題ではschema指定pathだけを上限付きで読み、Base64 artifactを返すことを確認する。
    payload = b"\xff\xd8image\xff\xd9"
    container = FakeContainer(output=[], image=payload)
    client, _ = make_client(container)

    result = client.exec_shellgei("true", "IMAGE-00000001", 1, 1000)

    assert result.artifact is not None
    assert result.artifact.data == base64.b64encode(payload).decode("ascii")
    assert result.artifact.path == "media/output.jpg"
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

    result = client.exec_shellgei("sleep infinity", "STANDARD-00000001", 0.05, 1000)

    assert time.monotonic() - started < 1
    assert result.status is ExecutionStatus.TIMED_OUT
    assert result.timed_out is True
    assert result.legacy_output() == "\n[Timed out]"
    assert result.artifact is None
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
    assert recovered.stdout == "recovered"
    client.close()


def test_large_combined_stdout_stderr_is_bounded_and_kills_container() -> None:
    # 出力上限超過時に表示を切り詰め、実行containerをkillすることを確認する。
    container = FakeContainer(output=[b"x" * 100_000])
    client, manager = make_client(container)

    result = client.exec_shellgei("yes", "STANDARD-00000001", 1, 10)

    assert result.status is ExecutionStatus.OUTPUT_LIMIT
    assert result.truncated is True
    assert result.stdout == "x" * 10
    assert result.legacy_output(limit_chars=10) == "x" * 10 + "..."
    assert result.artifact is None
    assert container.kill_calls >= 1
    assert manager.released == [container]
    client.close()


def test_oversized_image_is_rejected() -> None:
    # 許容byte数を超える画像を空文字列へ変換し、text結果は保持することを確認する。
    container = FakeContainer(output=[b"ok"], image=b"x" * (MAX_IMAGE_BYTES + 1))
    client, _ = make_client(container)

    result = client.exec_shellgei("echo ok", "IMAGE-00000001", 1, 1000)

    assert result.stdout == "ok"
    assert result.artifact is None
    client.close()


def test_image_stream_is_bounded_before_base64_encoding() -> None:
    # 画像streamを全量保持せずbyte上限で拒否してからbase64処理を止めることを確認する。
    container = FakeContainer(output=[b"ok"], image=b"x" * (MAX_IMAGE_BYTES + 65_536))
    client, _ = make_client(container)

    result = client.exec_shellgei("echo ok", "IMAGE-00000001", 1, 1000)

    assert result.stdout == "ok"
    assert result.artifact is None
    client.close()


def test_setup_failure_is_cleaned_up_as_a_running_container() -> None:
    # sandbox file準備失敗をerror結果へ変換し、未停止containerとして返却することを確認する。
    container = FakeContainer()
    container.setup_error = RuntimeError("archive transfer failed")
    client, manager = make_client(container)

    result = client.exec_shellgei("echo ok", "STANDARD-00000001", 1, 1000)

    assert result.status is ExecutionStatus.ERROR
    assert result.error == "archive transfer failed"
    assert result.legacy_output() == "Error during execution: archive transfer failed"
    assert manager.released == [container]
    assert manager.release_stopped_values == [False]
    client.close()


def test_nonzero_setup_result_is_cleaned_up_as_a_running_container() -> None:
    # archive展開commandの非zero終了を準備失敗とし、manager側で停止・破棄させる。
    container = FakeContainer()
    container.setup_exit_code = 1
    client, manager = make_client(container)

    result = client.exec_shellgei("echo ok", "STANDARD-00000001", 1, 1000)

    assert result.status is ExecutionStatus.ERROR
    assert result.error == "failed to prepare sandbox files"
    assert manager.release_stopped_values == [False]
    client.close()


def test_container_acquisition_failure_does_not_attempt_release() -> None:
    # container取得失敗を専用errorへ変換し、未取得containerを返却しないことを確認する。
    container = FakeContainer()
    client, manager = make_client(container)
    manager.get_error = RuntimeError("daemon unavailable")

    result = client.exec_shellgei("echo ok", "STANDARD-00000001", 1, 1000)

    assert result.status is ExecutionStatus.ERROR
    assert result.error == "failed to get container: daemon unavailable"
    assert manager.released == []
    client.close()


def test_command_execution_failure_stops_and_releases_container() -> None:
    # Docker exec失敗をerror結果へ変換し、containerを停止済みとして返却する。
    container = FakeContainer()
    container.execution_error = RuntimeError("exec failed")
    client, manager = make_client(container)

    result = client.exec_shellgei("echo ok", "STANDARD-00000001", 1, 1000)

    assert result.status is ExecutionStatus.ERROR
    assert result.error == "exec failed"
    assert container.kill_calls == 1
    assert manager.release_stopped_values == [True]
    client.close()


def test_artifact_capture_failure_returns_empty_artifact_and_cleans_up() -> None:
    # 画像読込失敗を画像なしへ変換し、text出力とcontainer cleanupを維持する。
    container = FakeContainer(output=[b"ok"])
    container.artifact_error = RuntimeError("capture failed")
    client, manager = make_client(container)

    result = client.exec_shellgei("echo ok", "IMAGE-00000001", 1, 1000)

    assert result.stdout == "ok"
    assert result.artifact is None
    assert manager.release_stopped_values == [True]
    client.close()


def test_cleanup_kill_failure_is_reported_and_released_as_running() -> None:
    # 正常exec後のkill失敗をerrorにし、managerへ未停止として返して再cleanupさせる。
    container = FakeContainer(output=[b"ok"])
    container.kill_error = RuntimeError("kill failed")
    client, manager = make_client(container)

    result = client.exec_shellgei("echo ok", "STANDARD-00000001", 1, 1000)

    assert result.status is ExecutionStatus.ERROR
    assert result.error == "kill failed"
    assert result.legacy_output() == "Error during execution: kill failed"
    assert manager.release_stopped_values == [False]
    client.close()


def test_timeout_waits_for_kill_completion_before_stopped_release() -> None:
    # timeout側killが完了するまで停止済み返却を待ち、cleanup競合を防ぐことを確認する。
    container = FakeContainer()
    container.allow_kill = threading.Event()

    def output_until_kill_starts() -> Any:
        """kill開始通知まで出力を待ち、kill完了前にstreamだけを終了する。"""
        container.kill_started.wait(timeout=2)
        if False:
            yield b""

    container.output = output_until_kill_starts()
    client, manager = make_client(container)
    results: list[ExecutionResult] = []

    def execute() -> None:
        """同期sandbox実行結果を別threadから観測用listへ追加する。"""
        results.append(
            client.exec_shellgei(
                "sleep infinity",
                "STANDARD-00000001",
                0.01,
                1000,
            )
        )

    worker = threading.Thread(target=execute)
    worker.start()
    assert container.kill_started.wait(timeout=1)
    time.sleep(0.02)
    assert manager.released == []

    container.allow_kill.set()
    worker.join(timeout=1)

    assert worker.is_alive() is False
    assert len(results) == 1
    assert results[0].status is ExecutionStatus.TIMED_OUT
    assert results[0].legacy_output() == "\n[Timed out]"
    assert manager.release_stopped_values == [True]
    client.close()


def test_hard_concurrency_limit_returns_busy_without_queueing() -> None:
    # 実行slot使用中の追加requestをqueueへ入れずSandboxBusyErrorにすることを確認する。
    entered = threading.Event()
    finish = threading.Event()
    manager = FakeManager(FakeContainer())
    client = ShellgeiDockerClient(container_manager=manager, max_concurrent=1)

    def blocking_execution(*args: Any) -> ExecutionResult:
        """入力を使用せずrelease通知まで待機し、固定実行結果を返す。"""
        entered.set()
        finish.wait(timeout=2)
        return completed_result()

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
        assert await first == completed_result()

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

    def blocking_execution(*args: Any) -> ExecutionResult:
        """入力を使用せずrelease通知まで同期処理を継続し、固定結果を返す。"""
        entered.set()
        finish.wait(timeout=2)
        return completed_result()

    client.exec_shellgei = blocking_execution  # type: ignore[assignment]

    async def scenario() -> None:
        """外側timeout、busy継続、worker終了後のslot回復を順番に検証する。"""
        first = await client.run_with_timeout("one", "problem", timeout=0.01)
        assert first.status is ExecutionStatus.ERROR
        assert first.error == "sandbox cleanup timed out"
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
            assert recovered == completed_result()
            return
        raise AssertionError("capacity was not released after the worker returned")

    try:
        asyncio.run(scenario())
    finally:
        finish.set()
        run_shellgei_module.DOCKER_OPERATION_GRACE_SECONDS = original_grace
        client.close()
