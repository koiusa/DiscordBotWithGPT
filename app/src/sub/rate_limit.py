"""Simple per-user rate limiting for fallback (non-addressed) responses.

We keep an in‑memory deque of event timestamps per user id. On each check we:
 1. Prune timestamps older than window_sec
 2. Allow if remaining < max_events

This is intentionally lightweight (no persistence). Adequate for single-process
Discord bot. If horizontal scaling is introduced, replace with redis or shared
store abstraction.
"""
from __future__ import annotations
from collections import deque
from typing import Deque, Dict
import time

class RateLimiter:
    def __init__(self, window_sec: int, max_events: int):
        self.window_sec = window_sec
        self.max_events = max_events
        self._events: Dict[int, Deque[float]] = {}

    def allow(self, user_id: int) -> bool:
        now = time.time()
        dq = self._events.get(user_id)
        if dq is None:
            dq = deque()
            self._events[user_id] = dq
        # prune
        cutoff = now - self.window_sec
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= self.max_events:
            return False
        dq.append(now)
        return True

# Factory helper (lazy init) if we decide to reconfigure dynamically later
def build_rate_limiter(window_sec: int, max_events: int) -> RateLimiter:
    return RateLimiter(window_sec=window_sec, max_events=max_events)
