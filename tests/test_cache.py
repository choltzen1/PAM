"""Unit tests for services/cache.py TTLCache."""
import time
import pytest

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.cache import TTLCache


class TestTTLCache:
    def test_set_and_get(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set('k', 'value')
        assert cache.get('k') == 'value'

    def test_miss_returns_none(self):
        cache = TTLCache(ttl_seconds=60)
        assert cache.get('missing') is None

    def test_expired_entry_returns_none(self):
        cache = TTLCache(ttl_seconds=1)
        cache.set('k', 'value')
        time.sleep(1.1)
        assert cache.get('k') is None

    def test_expired_entry_is_removed(self):
        cache = TTLCache(ttl_seconds=1)
        cache.set('k', 'value')
        time.sleep(1.1)
        cache.get('k')  # triggers eviction
        assert 'k' not in cache.store

    def test_unexpired_entry_is_returned(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set('k', 42)
        time.sleep(0.05)
        assert cache.get('k') == 42

    def test_overwrite_resets_ttl(self):
        cache = TTLCache(ttl_seconds=1)
        cache.set('k', 'old')
        time.sleep(0.6)
        cache.set('k', 'new')  # reset TTL
        time.sleep(0.6)
        assert cache.get('k') == 'new'  # still valid (0.6s since last write)

    def test_clear_removes_all_entries(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set('a', 1)
        cache.set('b', 2)
        cache.clear()
        assert cache.get('a') is None
        assert cache.get('b') is None
        assert len(cache.store) == 0

    def test_max_items_evicts_oldest(self):
        cache = TTLCache(ttl_seconds=60, max_items=3)
        cache.set('first', 1)
        time.sleep(0.01)
        cache.set('second', 2)
        time.sleep(0.01)
        cache.set('third', 3)
        time.sleep(0.01)
        cache.set('fourth', 4)  # should evict 'first' (oldest)
        assert cache.get('first') is None
        assert cache.get('fourth') == 4

    def test_max_items_not_exceeded(self):
        cache = TTLCache(ttl_seconds=60, max_items=5)
        for i in range(10):
            cache.set(f'key{i}', i)
            time.sleep(0.01)
        assert len(cache.store) <= 5

    def test_stores_various_value_types(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set('list', [1, 2, 3])
        cache.set('dict', {'a': 1})
        cache.set('none', None)
        assert cache.get('list') == [1, 2, 3]
        assert cache.get('dict') == {'a': 1}
        # None value stored but get returns None — indistinguishable from miss
        # This is a known limitation; test that set doesn't raise
