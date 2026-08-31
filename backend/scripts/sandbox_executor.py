import base64
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from models.execution import ExecutionStatus
from scripts.container_manager import SANDBOX_WORK_DIRECTORY
from scripts.execution_archive import build_execution_archive
from scripts.problem_repository import ProblemRecord
from scripts.sandbox_limits import BoundedByteBuffer


MAX_UTF8_BYTES_PER_CHAR = 4
EXECUTION_ARCHIVE_ENVIRONMENT = "SOJ_EXECUTION_ARCHIVE"
EXECUTION_ARCHIVE_EXTRACT_COMMAND = (
    "set -eu; umask 077; "
    f'printf "%s" "${EXECUTION_ARCHIVE_ENVIRONMENT}" | /usr/bin/base64 -d | '
    "/usr/bin/tar -x -f - --no-same-owner --no-same-permissions"
)


class SandboxAcquisitionError(RuntimeError):
    """sandbox containerを取得できなかった場合に、元の例外を保持して送出する。"""


@dataclass(frozen=True)
class CapturedCommandOutput:
    """分離したstdout/stderr、終了code、切り詰め、Docker errorを保持する。"""

    stdout: bytes
    stderr: bytes
    exit_code: int | None
    truncated: bool
    error: Exception | None


@dataclass(frozen=True)
class SandboxExecutionOutcome:
    """sandbox層の構造化結果とBase64化前のbinary artifactを保持する。"""

    status: ExecutionStatus
    stdout: bytes
    stderr: bytes
    exit_code: int | None
    timed_out: bool
    truncated: bool
    duration_ms: int
    artifact: bytes | None
    error: str | None


@dataclass(frozen=True)
class SandboxCleanupResult:
    """停止理由、停止時error、container停止確認結果をcleanupから返す。"""

    reason: str | None
    error: Exception | None
    container_stopped: bool


class ExecutionWatchdog:
    def __init__(self, container: Any) -> None:
        """監視対象containerを受け取り、未終了・理由なしの状態を初期化する。"""
        self.container = container
        self._lock = threading.Lock()
        self._finished = False
        self._reason: str | None = None
        self.termination_error: Exception | None = None

    def terminate(self, reason: str) -> bool:
        """最初の終了理由を記録してcontainerをkillし、終了処理の開始有無を返す。

        既に正常終了または別の終了処理が開始済みならFalseを返す。kill失敗は
        termination_errorへ保持し、cleanupが停止未確認として扱えるようにする。
        """
        with self._lock:
            if self._finished or self._reason is not None:
                return False
            self._reason = reason
        try:
            self.container.kill()
        except Exception as exc:
            self.termination_error = exc
        return True

    def finish(self) -> str | None:
        """新しいwatchdog終了を禁止し、既に記録された終了理由を返す。"""
        with self._lock:
            self._finished = True
            return self._reason

    @property
    def reason(self) -> str | None:
        """lockで保護された現在の終了理由を返し、未終了ならNoneを返す。"""
        with self._lock:
            return self._reason


class SandboxPreparer:
    def prepare(
        self,
        container: Any,
        shellgei: str,
        fixtures: Iterable[tuple[str, str]],
    ) -> None:
        """commandとfixtureをmemory内archive化してcontainerの作業領域へ展開する。

        入力は貸出済みcontainer、利用者command、検証済みfixture群。成功時の
        戻り値はなく、archive展開が失敗した場合はRuntimeErrorを送出する。
        """
        execution_archive = build_execution_archive(shellgei, fixtures)
        encoded_archive = base64.b64encode(execution_archive.getvalue()).decode("ascii")
        setup_result = container.exec_run(
            ["/bin/sh", "-c", EXECUTION_ARCHIVE_EXTRACT_COMMAND],
            environment={EXECUTION_ARCHIVE_ENVIRONMENT: encoded_archive},
            stdout=False,
            stderr=True,
            workdir=SANDBOX_WORK_DIRECTORY,
        )
        if setup_result.exit_code != 0:
            raise RuntimeError("failed to prepare sandbox files")


class DockerExecAdapter:
    def start(
        self,
        container: Any,
    ) -> tuple[str, Iterable[tuple[bytes | None, bytes | None]]]:
        """Docker execをstdout/stderr分離streamで開始し、exec IDとstreamを返す。

        入力containerの低レベルDocker APIを使用する。create/start失敗または
        Dockerからexec IDが返らない場合は例外を呼出側へ伝播する。
        """
        api = container.client.api
        created = api.exec_create(
            container.id,
            ["bash", "z.bash"],
            stdout=True,
            stderr=True,
            stdin=False,
            tty=False,
            workdir=SANDBOX_WORK_DIRECTORY,
        )
        exec_id = created.get("Id") if isinstance(created, dict) else None
        if not isinstance(exec_id, str) or not exec_id:
            raise RuntimeError("Docker exec ID is unavailable")
        output = api.exec_start(
            exec_id,
            stream=True,
            demux=True,
        )
        return exec_id, output

    def inspect_exit_code(self, container: Any, exec_id: str) -> int | None:
        """入力exec IDをDockerへ照会し、整数終了codeまたは未確定のNoneを返す。"""
        exit_code = container.client.api.exec_inspect(exec_id).get("ExitCode")
        if exit_code is None:
            return None
        if not isinstance(exit_code, int) or isinstance(exit_code, bool):
            raise RuntimeError("Docker exec exit code is invalid")
        return exit_code


class _SplitOutputBuffer:
    def __init__(self, byte_limit: int) -> None:
        """stdout/stderr共通byte上限を受け取り、空の分離bufferを初期化する。"""
        if byte_limit < 1:
            raise ValueError("byte_limit must be at least 1")
        self.byte_limit = byte_limit
        self.stdout = bytearray()
        self.stderr = bytearray()
        self.truncated = False

    def append(self, chunk: bytes, *, stderr: bool) -> bool:
        """入力chunkを指定streamへ合計上限まで追加し、全量保持できたか返す。"""
        remaining = self.byte_limit - len(self.stdout) - len(self.stderr)
        target = self.stderr if stderr else self.stdout
        if len(chunk) > remaining:
            target.extend(chunk[:remaining])
            self.truncated = True
            return False
        target.extend(chunk)
        return True


class SandboxOutputCapturer:
    def __init__(self, exec_adapter: DockerExecAdapter | None = None) -> None:
        """差替可能なDocker exec adapterを受け取り、出力取得処理を初期化する。"""
        self.exec_adapter = exec_adapter or DockerExecAdapter()

    def capture_command_output(
        self,
        container: Any,
        watchdog: ExecutionWatchdog,
        limit_chars: int,
    ) -> CapturedCommandOutput:
        """sandbox commandのstdout/stderrと終了codeを上限付きで取得して返す。

        文字数上限からUTF-8の最大byte数を算出し、両streamの合計へ適用する。
        上限超過時はwatchdogへoutput_limitを通知する。Docker失敗も部分出力と
        一緒にerrorとして返し、cleanupを必ず実行できるようにする。
        """
        output = _SplitOutputBuffer(limit_chars * MAX_UTF8_BYTES_PER_CHAR)
        if watchdog.reason is not None:
            return CapturedCommandOutput(b"", b"", None, False, None)
        exec_id: str | None = None
        exec_stream: Any = None
        exit_code: int | None = None
        error: Exception | None = None
        try:
            exec_id, exec_stream = self.exec_adapter.start(container)
            for stdout_chunk, stderr_chunk in exec_stream:
                if stdout_chunk and not output.append(stdout_chunk, stderr=False):
                    watchdog.terminate("output_limit")
                    break
                if stderr_chunk and not output.append(stderr_chunk, stderr=True):
                    watchdog.terminate("output_limit")
                    break
        except Exception as exc:
            error = exc
        finally:
            close = getattr(exec_stream, "close", None)
            if close is not None:
                try:
                    close()
                except Exception as exc:
                    error = error or exc
        if exec_id is not None:
            try:
                exit_code = self.exec_adapter.inspect_exit_code(container, exec_id)
            except Exception as exc:
                error = error or exc
        return CapturedCommandOutput(
            bytes(output.stdout),
            bytes(output.stderr),
            exit_code,
            output.truncated,
            error,
        )

    def capture_artifact(
        self,
        container: Any,
        path: str,
        max_bytes: int,
    ) -> bytes | None:
        """検証済み相対pathのartifactを上限付きで読み、binary dataを返す。

        artifactの欠損、Docker読込失敗、空data、上限超過はNoneへ変換する。
        pathと上限は起動時検証済みproblem schemaからだけ受け取る。
        """
        artifact = BoundedByteBuffer(max_bytes + 1)
        try:
            artifact_stream = container.exec_run(
                [
                    "/usr/bin/head",
                    "-c",
                    str(max_bytes + 1),
                    "--",
                    f"{SANDBOX_WORK_DIRECTORY}/{path}",
                ],
                stdout=True,
                stderr=False,
                stream=True,
            )
            chunks = (
                (artifact_stream.output,)
                if isinstance(artifact_stream.output, bytes)
                else artifact_stream.output
            )
            for chunk in chunks:
                if chunk and not artifact.append(chunk):
                    return None
        except Exception:
            return None
        payload = artifact.to_bytes()
        if not payload or len(payload) > max_bytes:
            return None
        return payload


class SandboxCleanup:
    def stop(
        self,
        container: Any,
        watchdog: ExecutionWatchdog,
        timeout_timer: threading.Timer,
    ) -> SandboxCleanupResult:
        """timerを止め、container停止完了を待ち、停止結果を返す。

        timeoutまたは出力超過のkillが別threadで進行中ならjoinして完了を待つ。
        終了理由がなければ正常実行後のbackground processも含めて同期的にkillする。
        """
        timeout_timer.cancel()
        reason = watchdog.finish()
        error: Exception | None = None
        container_stopped = False
        if reason is None:
            try:
                container.kill()
                container_stopped = True
            except Exception as exc:
                error = exc
        timeout_timer.join()
        if reason is not None:
            error = watchdog.termination_error
            container_stopped = error is None
        return SandboxCleanupResult(reason, error, container_stopped)


class SandboxExecutor:
    def __init__(
        self,
        container_manager: Any,
        preparer: SandboxPreparer | None = None,
        output_capturer: SandboxOutputCapturer | None = None,
        cleanup: SandboxCleanup | None = None,
    ) -> None:
        """container managerと差替可能な実行部品を受け取り、実行境界を初期化する。"""
        self.container_manager = container_manager
        self.preparer = preparer or SandboxPreparer()
        self.output_capturer = output_capturer or SandboxOutputCapturer()
        self.cleanup = cleanup or SandboxCleanup()

    def _execute_in_container(
        self,
        container: Any,
        record: ProblemRecord,
        shellgei: str,
        timeout: float,
        limit_chars: int,
        started_at: int,
    ) -> tuple[SandboxExecutionOutcome, bool]:
        """貸出済みcontainerを準備・実行・capture・停止し、構造化結果を返す。

        入力started_atはcontainer取得後の単調時計値。準備失敗は呼出側へ送出する。
        timeout、出力超過、exec/停止失敗はstatus、flag、errorへ分離し、
        失敗時はbinary artifactを返さない。
        """
        self.preparer.prepare(container, shellgei, record.fixtures)
        watchdog = ExecutionWatchdog(container)
        timeout_timer = threading.Timer(timeout, watchdog.terminate, args=("timeout",))
        timeout_timer.daemon = True
        timeout_timer.start()

        command_output = CapturedCommandOutput(b"", b"", None, False, None)
        artifact: bytes | None = None
        cleanup_result: SandboxCleanupResult
        try:
            command_output = self.output_capturer.capture_command_output(
                container,
                watchdog,
                limit_chars,
            )
            judge = record.definition.judge
            if (
                watchdog.reason is None
                and command_output.error is None
                and judge.type == "image"
            ):
                artifact = self.output_capturer.capture_artifact(
                    container,
                    judge.artifact.path,
                    judge.artifact.max_bytes,
                )
        finally:
            cleanup_result = self.cleanup.stop(container, watchdog, timeout_timer)

        execution_error = command_output.error or cleanup_result.error
        reason = cleanup_result.reason
        if reason == "timeout":
            status = ExecutionStatus.TIMED_OUT
        elif reason == "output_limit":
            status = ExecutionStatus.OUTPUT_LIMIT
        elif execution_error is not None or command_output.exit_code is None:
            status = ExecutionStatus.ERROR
            execution_error = execution_error or RuntimeError(
                "Docker exec exit code is unavailable"
            )
        else:
            status = ExecutionStatus.COMPLETED
        if status is not ExecutionStatus.COMPLETED:
            artifact = None
        duration_ms = max(0, (time.monotonic_ns() - started_at) // 1_000_000)
        outcome = SandboxExecutionOutcome(
            status=status,
            stdout=command_output.stdout,
            stderr=command_output.stderr,
            exit_code=command_output.exit_code,
            timed_out=status is ExecutionStatus.TIMED_OUT,
            truncated=command_output.truncated,
            duration_ms=duration_ms,
            artifact=artifact,
            error=str(execution_error) if execution_error is not None else None,
        )
        return outcome, cleanup_result.container_stopped

    @staticmethod
    def _error_outcome(error: Exception, started_at: int) -> SandboxExecutionOutcome:
        """準備等の例外と開始時刻から、出力なしの構造化error結果を返す。"""
        duration_ms = max(0, (time.monotonic_ns() - started_at) // 1_000_000)
        return SandboxExecutionOutcome(
            status=ExecutionStatus.ERROR,
            stdout=b"",
            stderr=b"",
            exit_code=None,
            timed_out=False,
            truncated=False,
            duration_ms=duration_ms,
            artifact=None,
            error=str(error),
        )

    def execute(
        self,
        record: ProblemRecord,
        shellgei: str,
        timeout: float,
        limit_chars: int,
    ) -> SandboxExecutionOutcome:
        """containerを1件借りて実行し、必ず破棄・返却して構造化結果を返す。

        入力は検証済み問題record、command、期限、表示文字数上限。container取得失敗は
        SandboxAcquisitionError、取得後の準備失敗はerror outcomeとして返す。
        """
        try:
            container = self.container_manager.get_container()
        except Exception as exc:
            raise SandboxAcquisitionError(str(exc)) from exc

        container_stopped = False
        started_at = time.monotonic_ns()
        try:
            try:
                outcome, container_stopped = self._execute_in_container(
                    container,
                    record,
                    shellgei,
                    timeout,
                    limit_chars,
                    started_at,
                )
                return outcome
            except Exception as exc:
                return self._error_outcome(exc, started_at)
        finally:
            self.container_manager.release_container(
                container,
                already_stopped=container_stopped,
            )
