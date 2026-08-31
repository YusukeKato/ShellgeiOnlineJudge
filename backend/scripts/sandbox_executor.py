import base64
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

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
class SandboxExecutionResponse:
    """既存runner APIへ返すtext出力と任意のBase64 artifactを保持する。"""

    output: str
    artifact: str


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


class SandboxOutputCapturer:
    @staticmethod
    def _stream_chunks(output: Any) -> Iterable[bytes]:
        """Docker SDKのbytesまたはbyte iteratorを、一様なbyte列iteratorとして返す。"""
        if isinstance(output, bytes):
            return (output,)
        return output

    def capture_command_output(
        self,
        container: Any,
        watchdog: ExecutionWatchdog,
        limit_chars: int,
    ) -> BoundedByteBuffer:
        """sandbox commandの混合出力を上限付きで読み、byte bufferを返す。

        文字数上限からUTF-8の最大byte数を算出する。上限超過時はwatchdogへ
        output_limitを通知してcontainerを停止する。Docker失敗は呼出側へ送出する。
        """
        output = BoundedByteBuffer(limit_chars * MAX_UTF8_BYTES_PER_CHAR)
        if watchdog.reason is not None:
            return output
        exec_stream = container.exec_run(
            ["bash", "z.bash"],
            demux=False,
            stream=True,
            workdir=SANDBOX_WORK_DIRECTORY,
        )
        for chunk in self._stream_chunks(exec_stream.output):
            if chunk and not output.append(chunk):
                watchdog.terminate("output_limit")
                break
        return output

    def capture_artifact(
        self,
        container: Any,
        path: str,
        max_bytes: int,
    ) -> str:
        """検証済み相対pathのartifactを上限付きで読み、Base64文字列を返す。

        artifactの欠損、Docker読込失敗、空data、上限超過は空文字列へ変換する。
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
            for chunk in self._stream_chunks(artifact_stream.output):
                if chunk and not artifact.append(chunk):
                    return ""
        except Exception:
            return ""
        payload = artifact.to_bytes()
        if not payload or len(payload) > max_bytes:
            return ""
        return base64.b64encode(payload).decode("ascii")


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

    @staticmethod
    def _format_output(
        output: BoundedByteBuffer,
        limit_chars: int,
        reason: str | None,
        execution_error: Exception | None,
    ) -> str:
        """収集済み出力と終了理由から、既存runner API用の表示文字列を返す。"""
        decoded = output.to_bytes().decode("utf-8", errors="ignore")
        if reason == "timeout":
            suffix = "\n[Timed out]"
            return decoded[: max(0, limit_chars - len(suffix))] + suffix
        if reason == "output_limit":
            return decoded[:limit_chars] + "..."
        if execution_error is not None:
            return f"Error during execution: {execution_error}"[:limit_chars]
        if not decoded:
            return ""
        if len(decoded) > limit_chars:
            return decoded[:limit_chars] + "..."
        return decoded

    def _execute_in_container(
        self,
        container: Any,
        record: ProblemRecord,
        shellgei: str,
        timeout: float,
        limit_chars: int,
    ) -> tuple[SandboxExecutionResponse, bool]:
        """貸出済みcontainerを準備・実行・回収・停止し、結果と停止確認flagを返す。

        準備失敗は呼出側へ送出する。exec失敗と停止失敗は既存互換のerror文字列へ
        変換し、timeoutまたは出力超過を含む失敗時はartifactを返さない。
        """
        self.preparer.prepare(container, shellgei, record.fixtures)
        watchdog = ExecutionWatchdog(container)
        timeout_timer = threading.Timer(timeout, watchdog.terminate, args=("timeout",))
        timeout_timer.daemon = True
        timeout_timer.start()

        output = BoundedByteBuffer(limit_chars * MAX_UTF8_BYTES_PER_CHAR)
        artifact = ""
        execution_error: Exception | None = None
        cleanup_result: SandboxCleanupResult
        try:
            output = self.output_capturer.capture_command_output(
                container,
                watchdog,
                limit_chars,
            )
            judge = record.definition.judge
            if watchdog.reason is None and judge.type == "image":
                artifact = self.output_capturer.capture_artifact(
                    container,
                    judge.artifact.path,
                    judge.artifact.max_bytes,
                )
        except Exception as exc:
            execution_error = exc
        finally:
            cleanup_result = self.cleanup.stop(container, watchdog, timeout_timer)

        execution_error = execution_error or cleanup_result.error
        formatted_output = self._format_output(
            output,
            limit_chars,
            cleanup_result.reason,
            execution_error,
        )
        if cleanup_result.reason is not None or execution_error is not None:
            artifact = ""
        return (
            SandboxExecutionResponse(formatted_output, artifact),
            cleanup_result.container_stopped,
        )

    def execute(
        self,
        record: ProblemRecord,
        shellgei: str,
        timeout: float,
        limit_chars: int,
    ) -> SandboxExecutionResponse:
        """containerを1件借りて実行し、必ず破棄・返却して既存形式の結果を返す。

        入力は検証済み問題record、command、期限、表示文字数上限。container取得失敗は
        SandboxAcquisitionError、それ以外の準備失敗は元の例外として呼出側へ送出する。
        """
        try:
            container = self.container_manager.get_container()
        except Exception as exc:
            raise SandboxAcquisitionError(str(exc)) from exc

        container_stopped = False
        try:
            response, container_stopped = self._execute_in_container(
                container,
                record,
                shellgei,
                timeout,
                limit_chars,
            )
            return response
        finally:
            self.container_manager.release_container(
                container,
                already_stopped=container_stopped,
            )
