import asyncio
from concurrent.futures import Future
from typing import TypeVar


THREAD_FUTURE_POLL_INTERVAL_SECONDS = 0.01
ResultT = TypeVar("ResultT")


async def wait_for_thread_future(
    future: Future[ResultT],
    *,
    timeout: float | None = None,
) -> ResultT:
    """threadの完了を短い間隔で確認し、event loopを塞がずに結果を待つ。"""
    loop = asyncio.get_running_loop()
    deadline = None if timeout is None else loop.time() + timeout

    while not future.done():
        if deadline is None:
            sleep_seconds = THREAD_FUTURE_POLL_INTERVAL_SECONDS
        else:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError
            sleep_seconds = min(THREAD_FUTURE_POLL_INTERVAL_SECONDS, remaining)
        await asyncio.sleep(sleep_seconds)

    return future.result()
