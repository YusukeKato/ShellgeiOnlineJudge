"""DB保存の受付と実処理の寿命を結び付ける回帰テスト。"""

import asyncio
import json
import threading
from collections.abc import Iterator
from concurrent.futures import Future
from typing import cast

import pytest
from sqlalchemy.orm import Session

import soj_backend.execution_log_repository as logs
from soj_backend.models.execution_log import ExecutionLogEntry
from tests.test_execution_log_retention import _execution_log_entry
from tests.test_public_api_v3 import _post_json
from tests.test_submit_solution import FakeJudge, FakeProblemRepo, FakeRunner
from soj_backend.submit_solution import SubmitSolutionService
import soj_backend.api.api_shellgei as api_shellgei


@pytest.fixture
def worker(monkeypatch: pytest.MonkeyPatch) -> Iterator[logs._ExecutionLogExecutor]:
    """test専用workerを共通保存入口へ注入し、終了時に回収する。"""
    executor = logs._ExecutionLogExecutor()
    monkeypatch.setattr(logs, "_executor", executor)
    try:
        yield executor
    finally:
        executor.shutdown()


def _defer_jobs(
    monkeypatch: pytest.MonkeyPatch, worker: logs._ExecutionLogExecutor
) -> list[Future[int]]:
    """worker開始前のfutureを保持し、実行前キャンセルを決定的に再現する。"""
    jobs: list[Future[int]] = []

    def submit(_persist: logs.PersistEntry, _entry: ExecutionLogEntry) -> Future[int]:
        """開始前のfutureだけを作り、呼び出し件数を記録する。"""
        future: Future[int] = Future()
        jobs.append(future)
        return future

    monkeypatch.setattr(worker._pool, "submit", submit)
    return jobs


def test_cancelled_waiters_keep_capacity_before_worker_start(
    monkeypatch: pytest.MonkeyPatch, worker: logs._ExecutionLogExecutor
) -> None:
    # 未開始の4保存のawaitをcancelしてloopを閉じても追加submitできず、実完了で全枠が戻る。
    jobs = _defer_jobs(monkeypatch, worker)

    async def cancel_waiters() -> None:
        """異なるadapterから同じ入口へ保存し、受付後の待機だけを取り消す。"""
        tasks = [
            asyncio.create_task(
                logs.AsyncExecutionLogRepo(logs.ExecutionLogRepo()).save(
                    _execution_log_entry(), request_id="a" * 32
                )
            )
            for _ in range(4)
        ]
        await asyncio.sleep(0)
        assert len(jobs) == 4
        for task in tasks:
            task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert all(isinstance(result, asyncio.CancelledError) for result in results)

    asyncio.run(cancel_waiters())
    for _ in range(12):
        with pytest.raises(logs.ExecutionLogRepositoryError):
            asyncio.run(logs.save_execution_log_async(_execution_log_entry()))
    assert len(jobs) == 4
    assert all(not future.cancelled() for future in jobs)
    for future in jobs:
        future.set_result(1)
    for _ in range(4):
        worker.submit(lambda _entry: 1, _execution_log_entry())
    assert len(jobs) == 8
    for future in jobs[4:]:
        future.set_result(1)


@pytest.mark.parametrize("failure", [False, True])
def test_running_saves_hold_capacity_after_cancellation_and_recover(
    worker: logs._ExecutionLogExecutor, failure: bool
) -> None:
    # 実threadの4保存を停止し、cancel後も拒否、成功・失敗の実終了後に全枠が戻ることを確認する。
    release = threading.Event()
    started = [threading.Event() for _ in range(4)]

    def persist(index: int) -> logs.PersistEntry:
        """開始通知と有限待機を持つ保存関数を返す。"""

        def save(_entry: ExecutionLogEntry) -> int:
            """解放まで保存を停止し、指定時は保存例外を送出する。"""
            started[index].set()
            assert release.wait(5)
            if failure:
                raise logs.ExecutionLogRepositoryError("test failure")
            return index + 1

        return save

    async def scenario() -> None:
        """受付済み保存をcancelし、停止中の再受付が拒否されることを検査する。"""
        tasks = [
            asyncio.create_task(
                logs.save_execution_log_async(
                    _execution_log_entry(), persist_entry=persist(index)
                )
            )
            for index in range(4)
        ]
        try:
            async with asyncio.timeout(3):
                while not all(event.is_set() for event in started):
                    await asyncio.sleep(0.001)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for _ in range(12):
                with pytest.raises(logs.ExecutionLogRepositoryError):
                    await logs.save_execution_log_async(_execution_log_entry())
        finally:
            release.set()
            await asyncio.gather(*tasks, return_exceptions=True)

    try:
        asyncio.run(scenario())
    finally:
        release.set()
        worker.shutdown()
    # shutdownは全完了を待つため、callbackによる全枠の返却も検査できる。
    assert all(worker._slots.acquire(blocking=False) for _ in range(4))
    assert not worker._slots.acquire(blocking=False)
    for _ in range(4):
        worker._slots.release()


def test_submit_failure_closes_admission(
    monkeypatch: pytest.MonkeyPatch, worker: logs._ExecutionLogExecutor
) -> None:
    # 投入有無を判断できないsubmit例外の後は、executorへ追加投入しない。
    calls = 0

    def fail(_persist: logs.PersistEntry, _entry: ExecutionLogEntry) -> Future[int]:
        """executorの受付失敗を再現する。"""
        nonlocal calls
        calls += 1
        raise RuntimeError("test submit failure")

    monkeypatch.setattr(worker._pool, "submit", fail)
    for _ in range(8):
        with pytest.raises(logs.ExecutionLogRepositoryError):
            asyncio.run(logs.save_execution_log_async(_execution_log_entry()))
    assert calls == 1


def test_immediate_completion_does_not_leak_slots(
    monkeypatch: pytest.MonkeyPatch, worker: logs._ExecutionLogExecutor
) -> None:
    # callback登録前に完了したfutureでも枠を失わず二重解放しない。

    def completed(
        _persist: logs.PersistEntry, _entry: ExecutionLogEntry
    ) -> Future[int]:
        """callback登録時点で既に完了済みのfutureを返す。"""
        future: Future[int] = Future()
        future.set_result(42)
        return future

    monkeypatch.setattr(worker._pool, "submit", completed)
    for _ in range(8):
        assert asyncio.run(logs.save_execution_log_async(_execution_log_entry())) == 42


def test_thread_start_failure_does_not_accumulate_enqueued_work(
    monkeypatch: pytest.MonkeyPatch, worker: logs._ExecutionLogExecutor
) -> None:
    # キュー投入後のthread生成失敗を実executorで再現し、残った仕事が増え続けないことを確認する。
    started = threading.Event()
    release = threading.Event()
    calls: list[int] = []

    def blocked(_entry: ExecutionLogEntry) -> int:
        """既存workerを有限待機させ、追加thread生成を必要にする。"""
        started.set()
        assert release.wait(5)
        calls.append(1)
        return 1

    def fail_start(_thread: threading.Thread) -> None:
        """ホスト資源を消費せずThread.startの資源不足例外だけを注入する。"""
        raise RuntimeError("test cannot start new thread")

    first = worker.submit(blocked, _execution_log_entry())
    try:
        assert started.wait(3)
        with monkeypatch.context() as patch:
            patch.setattr(threading.Thread, "start", fail_start)
            with pytest.raises(RuntimeError, match="cannot start"):
                worker.submit(blocked, _execution_log_entry())
            for _ in range(12):
                with pytest.raises(logs.ExecutionLogRepositoryError):
                    worker.submit(blocked, _execution_log_entry())
            assert worker._pool._work_queue.qsize() == 1
    finally:
        release.set()
        worker.shutdown()
    assert first.result() == 1
    assert 1 <= len(calls) <= 2


def test_shutdown_closes_admission_before_waiting(
    monkeypatch: pytest.MonkeyPatch, worker: logs._ExecutionLogExecutor
) -> None:
    # 終了待ち中のsubmitを拒否し、shutdownの未開始future取消と重複closeを許容する。
    jobs = _defer_jobs(monkeypatch, worker)
    for _ in range(4):
        worker.submit(lambda _entry: 1, _execution_log_entry())
    stopping = threading.Event()
    release = threading.Event()

    def shutdown(*, wait: bool, cancel_futures: bool) -> None:
        """停止中の競合を再現し、未開始futureをexecutor同様に取り消す。"""
        assert wait and cancel_futures
        stopping.set()
        assert release.wait(5)
        for future in jobs:
            future.cancel()

    with monkeypatch.context() as patch:
        patch.setattr(worker._pool, "shutdown", shutdown)
        closer = threading.Thread(target=worker.shutdown)
        closer.start()
        try:
            assert stopping.wait(3)
            with pytest.raises(logs.ExecutionLogRepositoryError):
                worker.submit(lambda _entry: 1, _execution_log_entry())
        finally:
            release.set()
            closer.join(5)
        assert not closer.is_alive()
        worker.shutdown()
    assert len(jobs) == 4


@pytest.mark.parametrize("path", ["/api/v3/submissions", "/api/shellgei"])
def test_full_save_capacity_preserves_public_result(
    monkeypatch: pytest.MonkeyPatch,
    worker: logs._ExecutionLogExecutor,
    path: str,
) -> None:
    # 実受付上限の拒否をserviceとHTTP経路へ通し、採点・出力と既存の保存不能形式を維持する。
    jobs = _defer_jobs(monkeypatch, worker)
    for _ in range(4):
        worker.submit(lambda _entry: 1, _execution_log_entry())
    events: list[str] = []
    service = SubmitSolutionService(
        FakeProblemRepo(events),
        FakeRunner(events),
        FakeJudge(events),
        logs.AsyncExecutionLogRepo(logs.ExecutionLogRepo()),
    )
    monkeypatch.setattr(api_shellgei, "submit_solution_service", service)
    try:
        status, _headers, body = _post_json(
            path, {"shellgei": "printf ok", "problem_id": "STANDARD-00000001"}
        )
        result = json.loads(body)
        assert status == 200
        if path == "/api/v3/submissions":
            assert result["submission_id"] is None
            assert result["persistence"] == "unavailable"
            assert result["verdict"] == "accepted"
            assert result["execution"]["stdout"] == "ok"
        else:
            assert result["id"] == "-1"
            assert result["judge"] == "1"
            assert result["output"] == "ok"
        assert events == ["problem", "runner", "judge"]
        assert len(jobs) == 4
    finally:
        for future in jobs:
            future.set_result(1)


@pytest.mark.parametrize("stage", ["rollback", "close"])
def test_cleanup_finishes_before_capacity_returns(
    worker: logs._ExecutionLogExecutor, stage: str
) -> None:
    # commit失敗後のrollback・closeが停止中は枠を保持し、後始末自体の例外後も枠を返す。
    release = threading.Event()
    reached = threading.Barrier(5, timeout=5)

    class FailingSession:
        """後始末の途中で停止するDB sessionを再現する。"""

        def add(self, entry: object) -> None:
            """保存開始時に模擬IDを設定する。"""
            setattr(entry, "id", 1)

        def commit(self) -> None:
            """rollback経路へ入るためcommitを失敗させる。"""
            raise RuntimeError("test commit failure")

        def rollback(self) -> None:
            """指定された後始末を停止させ、その後失敗を返す。"""
            if stage == "rollback":
                reached.wait()
                assert release.wait(5)
            raise RuntimeError("test rollback failure")

        def close(self) -> None:
            """指定されたcloseを停止させ、その後失敗を返す。"""
            if stage == "close":
                reached.wait()
                assert release.wait(5)
            raise RuntimeError("test close failure")

    repository = logs.ExecutionLogRepo(
        session_factory=lambda: cast(Session, FailingSession()),
        prune_logs=lambda _db: 0,
    )
    futures = [worker.submit(repository.save, _execution_log_entry()) for _ in range(4)]
    try:
        reached.wait()
        with pytest.raises(logs.ExecutionLogRepositoryError):
            worker.submit(repository.save, _execution_log_entry())
    finally:
        release.set()
        worker.shutdown()
    for future in futures:
        with pytest.raises(logs.ExecutionLogRepositoryError):
            future.result()
    assert all(worker._slots.acquire(blocking=False) for _ in range(4))
    for _ in range(4):
        worker._slots.release()
