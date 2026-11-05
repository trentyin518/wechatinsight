"""Tiny in-process rate limiter for cold-start/third-party protection.

MVP runs a single backend instance; a sliding window per key is enough. If we
scale horizontally, swap this for a shared store behind the same interface.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from app.core.errors import RateLimited


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: float = 60.0) -> None:
        now = time.monotonic()
        events = self._events[key]
        while events and now - events[0] > window_seconds:
            events.popleft()
        if len(events) >= limit:
            raise RateLimited()
        events.append(now)

    def reset(self) -> None:
        self._events.clear()


rate_limiter = InMemoryRateLimiter()
