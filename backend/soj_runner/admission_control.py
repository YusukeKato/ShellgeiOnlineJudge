import math
import threading
import time
from collections.abc import Callable


DEFAULT_SANDBOX_START_RATE_PER_SECOND = 1.0
DEFAULT_SANDBOX_START_BURST = 3


class SandboxStartRateLimiter:
    """Thread-safe token bucket for sandbox execution starts."""

    def __init__(
        self,
        rate_per_second: float = DEFAULT_SANDBOX_START_RATE_PER_SECOND,
        burst: int = DEFAULT_SANDBOX_START_BURST,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not math.isfinite(rate_per_second) or rate_per_second <= 0:
            raise ValueError("rate_per_second must be a positive finite number")
        if burst < 1:
            raise ValueError("burst must be at least 1")

        self.rate_per_second = rate_per_second
        self.burst = burst
        self._clock = clock
        self._lock = threading.Lock()
        self._tokens = float(burst)
        self._updated_at = clock()

    def try_acquire(self) -> bool:
        """Consume one start token without waiting, or reject the request."""

        with self._lock:
            now = self._clock()
            elapsed = max(0.0, now - self._updated_at)
            self._tokens = min(
                float(self.burst),
                self._tokens + elapsed * self.rate_per_second,
            )
            self._updated_at = now

            if self._tokens < 1.0:
                return False
            self._tokens -= 1.0
            return True


sandbox_start_rate_limiter = SandboxStartRateLimiter()
