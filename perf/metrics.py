import time
import threading
from typing import Dict, Any, Optional, Callable

_lock = threading.RLock()

class RequestMetricsCollector:
    """In-process request metrics aggregator (lightweight, resettable for tests).

    Captures per-route timings, counts, basic cache hit/miss counters that can be
    incremented from code paths. Not a replacement for Prometheus but fast to adopt.
    """
    def __init__(self):
        self.reset()

    def reset(self):
        with _lock:
            self.request_count = 0
            self.routes: Dict[str, Dict[str, Any]] = {}
            self.cache_counters: Dict[str, Dict[str, int]] = {}

    def begin_request(self, route_key: str) -> float:
        return time.perf_counter()

    def end_request(self, route_key: str, start: float):
        dur = (time.perf_counter() - start) * 1000.0  # ms
        with _lock:
            self.request_count += 1
            r = self.routes.setdefault(route_key, {
                'count': 0,
                'total_ms': 0.0,
                'max_ms': 0.0,
            })
            r['count'] += 1
            r['total_ms'] += dur
            if dur > r['max_ms']:
                r['max_ms'] = dur
        return dur

    def record_cache(self, cache_name: str, hit: bool):
        with _lock:
            c = self.cache_counters.setdefault(cache_name, {'hits': 0, 'misses': 0})
            if hit:
                c['hits'] += 1
            else:
                c['misses'] += 1

    def snapshot(self) -> Dict[str, Any]:
        with _lock:
            out = {
                'requests': self.request_count,
                'routes': {},
                'caches': self.cache_counters.copy()
            }
            for k, v in self.routes.items():
                avg = v['total_ms'] / v['count'] if v['count'] else 0.0
                out['routes'][k] = {
                    'count': v['count'],
                    'avg_ms': round(avg, 2),
                    'max_ms': round(v['max_ms'], 2)
                }
            return out

collector = RequestMetricsCollector()

def cache_counter(cache_name: str, loader: Callable[[], Any], key: str, store: Dict[str, Any], ttl_seconds: Optional[int] = None):
    """Simple cache wrapper to record hit/miss. TTL logic is naive (timestamp stored alongside value)."""
    now = time.time()
    entry = store.get(key)
    if entry:
        value, ts = entry
        if ttl_seconds is None or (now - ts) < ttl_seconds:
            collector.record_cache(cache_name, True)
            return value
    # Miss
    value = loader()
    store[key] = (value, now)
    collector.record_cache(cache_name, False)
    return value
