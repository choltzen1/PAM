from typing import Any, Optional, Tuple
import time

class TTLCache:
    def __init__(self, ttl_seconds: int = 30, max_items: int = 1000):
        self.ttl = ttl_seconds
        self.max_items = max_items
        self.store: dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        item = self.store.get(key)
        if not item:
            return None
        ts, value = item
        if time.time() - ts > self.ttl:
            # expired
            self.store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        # Simple eviction: if over max_items, drop oldest by timestamp
        if len(self.store) >= self.max_items:
            oldest_key = min(self.store.items(), key=lambda kv: kv[1][0])[0]
            self.store.pop(oldest_key, None)
        self.store[key] = (time.time(), value)

    def clear(self) -> None:
        self.store.clear()
