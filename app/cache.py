"""A tiny in-memory TTL cache.

Public APIs have rate limits (CoinGecko especially). Caching responses for a few
minutes keeps the dashboard fast and avoids hitting those limits.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    async def get_or_set(self, key: str, factory: Callable[[], Awaitable[Any]]) -> Any:
        """Return the cached value for `key`, or compute it with `factory` and store it."""
        now = time.monotonic()
        hit = self._store.get(key)
        if hit is not None and now - hit[0] < self.ttl:
            return hit[1]
        value = await factory()
        self._store[key] = (now, value)
        return value

    def clear(self) -> None:
        self._store.clear()
