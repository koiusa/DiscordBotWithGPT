from __future__ import annotations
import time
from collections import OrderedDict
from typing import Optional
from sub.search.websearch import SearchData
from sub.infra.logging import logger
import os

CACHE_TTL = int(os.environ.get("WEBSEARCH_CACHE_TTL", "180"))  # seconds
CACHE_MAX = int(os.environ.get("WEBSEARCH_CACHE_MAX", "128"))

class WebSearchCache:
    def __init__(self, ttl: int = CACHE_TTL, max_items: int = CACHE_MAX):
        self.ttl = ttl
        self.max_items = max_items
        self._data: OrderedDict[str, tuple[float, SearchData]] = OrderedDict()

    def get(self, key: str) -> Optional[SearchData]:
        now = time.time()
        item = self._data.get(key)
        if not item:
            return None
        ts, value = item
        if now - ts > self.ttl:
            # expired
            try:
                del self._data[key]
            except KeyError:
                pass
            return None
        # promote
        self._data.move_to_end(key)
        logger.info(f"websearch_cache hit key='{key[:80]}'")
        return value

    def set(self, key: str, value: SearchData):
        self._data[key] = (time.time(), value)
        self._data.move_to_end(key)
        if len(self._data) > self.max_items:
            # evict oldest
            evicted_key, _ = self._data.popitem(last=False)
            logger.info(f"websearch_cache evict key='{evicted_key[:80]}'")

# singleton
cache = WebSearchCache()

__all__ = ["cache", "WebSearchCache"]
