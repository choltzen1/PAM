import types
import pytest
from data.field_map import FIELD_DB_MAP, READ_ONLY_FIELDS, EDITABLE_CANONICAL_FIELDS, canonical_to_physical, quote_identifier
from data.database import DatabaseManager

pytestmark = pytest.mark.no_external_writes


class StubConn:
    def __init__(self, recorder):
        self._recorder = recorder
    def execute(self, clause, params=None):  # mimic SQLAlchemy API
        sql_text = getattr(clause, 'text', str(clause))
        self._recorder['sql'] = sql_text
        # If params passed separately capture them; else clause may be raw
        if params is not None:
            self._recorder['params'] = params
        else:
            self._recorder['params'] = {}

class StubBeginCtx:
    def __init__(self, recorder):
        self._recorder = recorder
    def __enter__(self):
        return StubConn(self._recorder)
    def __exit__(self, exc_type, exc, tb):
        return False

class StubEngine:
    def __init__(self, recorder):
        self._recorder = recorder
    def begin(self):
        return StubBeginCtx(self._recorder)
    # Provide connect for any accidental calls
    def connect(self):
        return StubConn(self._recorder)


def make_db_manager_with_stubs(existing_physical_cols: set):
    dbm = DatabaseManager()
    # Monkeypatch get_existing_columns BEFORE update call to avoid real DB introspection
    dbm.get_existing_columns = types.MethodType(lambda self: existing_physical_cols, dbm)
    recorder = {}
    dbm.get_engine = types.MethodType(lambda self: StubEngine(recorder), dbm)
    return dbm, recorder


def test_read_only_not_editable():
    # Ensure no read-only fields accidentally appear in editable set
    intersection = READ_ONLY_FIELDS & EDITABLE_CANONICAL_FIELDS
    assert not intersection, f"Read-only fields leaked into editable set: {intersection}"


def test_mapping_round_trip_basic():
    # Canonical -> physical mapping should return expected value; quote if needed
    for canonical, physical in FIELD_DB_MAP.items():
        resolved = canonical_to_physical(canonical)
        assert resolved == physical
        quoted = quote_identifier(physical)
        if ' ' in physical:
            assert quoted.startswith('[') and quoted.endswith(']')


def test_update_promo_fields_bracket_and_params():
    # Provide a minimal subset including a space-containing physical column
    canonical_updates = {
        'bill_facing_name': 'My Facing Name',
        'discount': '25%',
        'amount': '100',
    }
    # Physical columns that exist in table (simulate actual schema)
    existing_cols = {canonical_to_physical(k) for k in canonical_updates.keys()} | {'code'}
    dbm, recorder = make_db_manager_with_stubs(existing_cols)
    ok = dbm.update_promo_fields('X123', canonical_updates)
    assert ok is True
    sql = recorder.get('sql')
    params = recorder.get('params')
    assert sql, 'No SQL captured'
    # Ensure bracketed column appears
    assert '[bill facing name]' in sql, 'Space-containing column not bracket quoted'
    # Ensure all assignments present
    for c in canonical_updates.keys():
        phys = quote_identifier(canonical_to_physical(c))
        assert f"{phys} =" in sql, f"Missing assignment for {c}"
    # Parameter count (promo code + each field)
    assert params is not None and params.get('code') == 'X123'
    assert any(v == 'My Facing Name' for v in (params or {}).values())


def test_update_promo_fields_skips_unknown():
    canonical_updates = {
        'discount': '10%',
        'unknown_field': 'SHOULD_SKIP',
    }
    existing_cols = {canonical_to_physical('discount'), 'code'}  # unknown not present
    dbm, recorder = make_db_manager_with_stubs(existing_cols)
    ok = dbm.update_promo_fields('Z9', canonical_updates)
    assert ok is True
    sql = recorder.get('sql')
    assert sql and 'discount' in sql.lower()
    # Ensure unknown field did not produce a parameter
    for k,v in recorder.get('params', {}).items():
        assert v != 'SHOULD_SKIP'


def test_all_editable_fields_can_attempt_update():
    # We simulate that every physical column exists; confirm SQL contains each when provided
    sample_values = {field: f"TEST_{field}" for field in list(EDITABLE_CANONICAL_FIELDS)[:15]}  # limit for test performance
    existing_cols = {canonical_to_physical(f) for f in EDITABLE_CANONICAL_FIELDS} | {'code'}
    dbm, recorder = make_db_manager_with_stubs(existing_cols)
    ok = dbm.update_promo_fields('T777', sample_values)
    assert ok is True
    sql = recorder.get('sql')
    assert sql
    for c in sample_values.keys():
        phys = quote_identifier(canonical_to_physical(c))
        assert phys in sql, f"Expected {phys} in generated SQL"