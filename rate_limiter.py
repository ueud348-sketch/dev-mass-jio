import time
import asyncio


class RateLimiter:
    """Simple async rate limiter - ensures min_interval between calls."""

    def __init__(self, min_interval: float = 3.0):
        self._min_interval = min_interval
        self._last_send = 0.0
        self._lock = asyncio.Lock()

    async def wait(self):
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_send
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_send = time.time()
