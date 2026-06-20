import time
import threading


class CircuitBreaker:
    """
    Opens after FAILURE_THRESHOLD consecutive failures from external API calls.
    Auto-resets after RESET_TIMEOUT seconds, allowing one probe request through.
    Thread-safe for multi-threaded Flask workers.
    """
    FAILURE_THRESHOLD = 3
    RESET_TIMEOUT = 300  # 5 minutes

    def __init__(self):
        self._failures = 0
        self._opened_at = None
        self._lock = threading.Lock()

    def check(self) -> tuple[bool, int]:
        """Return (is_open, seconds_until_reset) atomically under one lock acquisition."""
        with self._lock:
            if self._opened_at is None:
                return False, 0
            elapsed = time.time() - self._opened_at
            if elapsed > self.RESET_TIMEOUT:
                self._failures = 0
                self._opened_at = None
                return False, 0
            return True, max(0, int(self.RESET_TIMEOUT - elapsed))

    @property
    def is_open(self) -> bool:
        open_, _ = self.check()
        return open_

    def record_failure(self):
        with self._lock:
            self._failures += 1
            if self._failures >= self.FAILURE_THRESHOLD:
                self._opened_at = time.time()

    def record_success(self):
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def seconds_until_reset(self) -> int:
        _, secs = self.check()
        return secs
