import types
from datetime import datetime, timezone
import pytest
from data.field_map import EDITABLE_CANONICAL_FIELDS, canonical_to_physical
from data.database import DatabaseManager

pytestmark = pytest.mark.no_external_writes

class StubConn:
    def __init__(self, recorder, row_source):
        self._recorder = recorder
        self._row_source = row_source
    def execute(self, clause, params=None):
        sql_text = getattr(clause, 'text', str(clause))
        self._recorder['sql_calls'].append({'sql': sql_text, 'params': params or {}})
        # Simulate SELECT * ... WHERE code = :promo_code
        if 'select *' in sql_text.lower() and 'where code' in sql_text.lower():
            return StubResult([self._row_source])
        return StubResult([])
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def fetchall(self):
        return []

class StubResult:
    def __init__(self, rows):
        self._rows = rows
    def fetchall(self):
        return self._rows
    def fetchone(self):
        return self._rows[0] if self._rows else None
    def mappings(self):
        return self
    def all(self):
        return self._rows
    def first(self):
        return self._rows[0] if self._rows else None

class StubBeginCtx:
    def __init__(self, recorder, row_source):
        self._recorder = recorder
        self._row_source = row_source
    def __enter__(self):
        return StubConn(self._recorder, self._row_source)
    def __exit__(self, exc_type, exc, tb):
        return False

class StubEngine:
    def __init__(self, recorder, row_source):
        self._recorder = recorder
        self._row_source = row_source
    def begin(self):
        return StubBeginCtx(self._recorder, self._row_source)
    def connect(self):
        # Return a context manager (StubConn already has __enter__ and __exit__)
        return StubConn(self._recorder, self._row_source)


def build_row(code: str, field_values: dict):
    # Build a simulated DB row dict containing physical columns.
    row = {'code': code}
    for canonical, value in field_values.items():
        phys = canonical_to_physical(canonical)
        row[phys] = value
    # Always include a couple baseline fields
    row.setdefault('Owner', 'Tester')
    row.setdefault('promo_start_date', datetime.now(timezone.utc).strftime('%Y-%m-%d'))
    row.setdefault('promo_end_date', datetime.now(timezone.utc).strftime('%Y-%m-%d'))
    return row


def make_db_manager(row_source):
    import pandas as pd
    dbm = DatabaseManager()
    dbm.get_existing_columns = types.MethodType(lambda self: set(row_source.keys()), dbm)
    recorder = {'sql_calls': []}
    
    # Mock get_dataframe to return a DataFrame from row_source
    def mock_get_dataframe(self, sql: str, params=None):
        recorder['sql_calls'].append({'sql': sql, 'params': params or {}})
        # Return DataFrame with the row if it's a SELECT for this code
        if 'select *' in sql.lower() and 'where code' in sql.lower():
            return pd.DataFrame([row_source])
        return pd.DataFrame()
    
    dbm.get_dataframe = types.MethodType(mock_get_dataframe, dbm)
    dbm.get_engine = types.MethodType(lambda self: StubEngine(recorder, row_source), dbm)
    return dbm, recorder


def test_round_trip_conversion_preserves_values():
    sample_subset = list(EDITABLE_CANONICAL_FIELDS)[:20]
    field_values = {f: f"VAL_{i}" for i, f in enumerate(sample_subset)}
    row = build_row('RT1', field_values)
    dbm, recorder = make_db_manager(row)
    # Simulate fetch
    raw = dbm.get_promo_by_code('RT1')
    assert raw, 'Raw DB fetch failed'
    converted = dbm.convert_db_record_to_json_format(raw)
    # Each canonical should appear either directly or via converter pass-through
    missing = []
    for c in sample_subset:
        if converted.get(c) != field_values[c]:
            missing.append(c)
    assert not missing, f"Round-trip lost fields: {missing}"


def test_update_then_fetch_reflects_change():
    # Start with one field value then update; ensure converted shows new value
    field_values = {'discount': '5%', 'amount': '50'}
    row = build_row('RT2', field_values)
    dbm, recorder = make_db_manager(row)
    # Update discount
    ok = dbm.update_promo_fields('RT2', {'discount': '10%'})
    assert ok is True
    # Simulate side-effect of update by mutating row_source (since stub doesn't actually modify row)
    row['discount'] = '10%'
    raw = dbm.get_promo_by_code('RT2')
    assert raw is not None
    converted = dbm.convert_db_record_to_json_format(raw)
    assert converted.get('discount') == '10%'


def test_skip_nonexistent_field_does_not_error():
    row = build_row('RT3', {'discount': '1%'})
    dbm, recorder = make_db_manager(row)
    ok = dbm.update_promo_fields('RT3', {'unknown_field': 'X', 'discount': '2%'})
    assert ok is True
    # Mutate row for successful discount change
    row['discount'] = '2%'
    raw = dbm.get_promo_by_code('RT3')
    assert raw is not None
    converted = dbm.convert_db_record_to_json_format(raw)
    assert converted.get('discount') == '2%'


def test_round_trip_regression_promo_grace_and_maintain_active_line():
    field_values = {
        'promo_grace': '45',
        'maintain_active_line': 'Y',
    }
    row = build_row('RT4', field_values)
    dbm, recorder = make_db_manager(row)

    raw = dbm.get_promo_by_code('RT4')
    assert raw, 'Raw DB fetch failed'
    converted = dbm.convert_db_record_to_json_format(raw)

    assert converted.get('promo_grace') == '45'
    assert converted.get('maintain_active_line') == 'Y'