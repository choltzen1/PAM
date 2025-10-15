import os, sys
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import factory  # ensures create_app & data_manager loaded
from data.database import DatabaseManager


def _db_available() -> bool:
    try:
        dm = DatabaseManager()
        return dm.test_connection()
    except Exception:
        return False


@pytest.mark.skipif(not _db_available(), reason="Database not reachable in test environment")
def test_engine_connects():
    dm = DatabaseManager()
    assert dm.test_connection() is True


@pytest.mark.skipif(not _db_available(), reason="Database not reachable in test environment")
def test_fetch_single_promo_roundtrip(monkeypatch):
    dm = DatabaseManager()
    # Attempt to pull top 1 code to validate conversion function does not crash
    import sqlalchemy
    engine = dm.get_engine()
    with engine.connect() as conn:
        try:
            res = conn.execute(sqlalchemy.text(f"SELECT TOP 1 code FROM {dm.source_table} WHERE code IS NOT NULL"))
            row = res.fetchone()
        except Exception as e:
            pytest.skip(f"Query failed (schema mismatch or no data): {e}")
    if not row:
        pytest.skip("No promo rows present in source table to validate fetch")
    code = str(row[0])
    rec = dm.get_promo_by_code(code)
    assert rec, "Expected non-empty DB record for known code"
    converted = dm.convert_db_record_to_json_format(rec)
    assert converted.get('code') == code
    # ensure key normalizations applied
    assert 'bill facing name' not in converted, "Physical column should be normalized in conversion"
    assert 'bill_facing_name' in converted


@pytest.mark.skipif(not _db_available(), reason="Database not reachable in test environment")
def test_paginated_query_performance_smoke(monkeypatch):
    dm = DatabaseManager()
    # Simple timing budget (very loose) for pulling a small page
    import time, sqlalchemy
    start = time.time()
    engine = dm.get_engine()
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text(f"SELECT TOP 25 code, Owner FROM {dm.source_table} ORDER BY code DESC"))
    elapsed = time.time() - start
    # Not asserting strict threshold; just ensuring it completes under a generous ceiling (5s) to catch hangs
    assert elapsed < 5.0
