import time
import threading
from typing import Optional
from sub.utils import logger

class MessageDeduplicator:
    """In-memory deduplicator for Discord message IDs.

    Strategy:
      - Keep an ordered dict-like store {message_id: timestamp}
      - TTL based eviction on access
      - Size bound to avoid unbounded growth
    Thread safety:
      - A simple lock; discord.py callbacks are on one loop thread, but
        defensive locking allows future cross-thread usage.
    """

    def __init__(self, ttl_seconds: float = 60.0, max_entries: int = 5000):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._store: dict[int, float] = {}
        self._lock = threading.Lock()

    def _evict_expired(self, now: float):
        if not self._store:
            return
        # Remove expired
        expired_keys = [k for k, ts in self._store.items() if now - ts > self.ttl]
        for k in expired_keys:
            self._store.pop(k, None)
        # If still too large, drop oldest (approx by timestamp sort)
        if len(self._store) > self.max_entries:
            # Sort by timestamp ascending and trim
            for k in sorted(self._store.items(), key=lambda x: x[1])[: len(self._store) - self.max_entries]:
                self._store.pop(k[0], None)

    def seen(self, message_id: int) -> bool:
        """Return True if message id already processed (and updates nothing)."""
        now = time.time()
        with self._lock:
            self._evict_expired(now)
            return message_id in self._store

    def mark(self, message_id: int):
        now = time.time()
        with self._lock:
            self._evict_expired(now)
            self._store[message_id] = now

# Singleton instance (simple use-case)
GLOBAL_MESSAGE_DEDUP = MessageDeduplicator()

__all__ = ["GLOBAL_MESSAGE_DEDUP", "MessageDeduplicator"]
