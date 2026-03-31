"""Tests for PAM.Promo_ID_Tracking integration in DatabaseManager.

These tests use mocks to avoid requiring a real database connection.
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from data.database import DatabaseManager


@pytest.fixture
def db():
    """DatabaseManager with mocked engine."""
    dm = DatabaseManager()
    dm._engine = MagicMock()
    return dm


class TestTrackingTableExists:
    def test_returns_true_when_table_exists(self, db):
        conn = db._engine.connect.return_value.__enter__.return_value
        conn.execute.return_value.fetchone.return_value = (1,)
        assert db._tracking_table_exists() is True

    def test_caches_positive_result(self, db):
        conn = db._engine.connect.return_value.__enter__.return_value
        conn.execute.return_value.fetchone.return_value = (1,)
        db._tracking_table_exists()
        db._tracking_table_exists()
        # Second call should use cache, not hit DB again
        assert conn.execute.call_count == 1

    def test_returns_false_when_table_missing(self, db):
        conn = db._engine.connect.return_value.__enter__.return_value
        conn.execute.return_value.fetchone.return_value = None
        assert db._tracking_table_exists() is False

    def test_returns_false_on_exception(self, db):
        db._engine.connect.side_effect = Exception("connection error")
        assert db._tracking_table_exists() is False


class TestInsertTrackingRecord:
    def test_inserts_record_successfully(self, db):
        db._tracking_exists_cache = True
        engine = db._engine
        conn = engine.begin.return_value.__enter__.return_value

        record = {
            'code': 'R100',
            'orbit_id': '12345',
            'sku_group_id': 'AA1',
            'trade_in_group_id': 'A01',
        }
        result = db.insert_tracking_record(record, 'testuser')
        assert result is True
        conn.execute.assert_called_once()

    def test_skips_when_table_missing(self, db):
        # No cache set, and mock returns no table
        conn = db._engine.connect.return_value.__enter__.return_value
        conn.execute.return_value.fetchone.return_value = None
        result = db.insert_tracking_record({'code': 'R100'}, 'user')
        assert result is False

    def test_skips_when_no_code(self, db):
        db._tracking_exists_cache = True
        result = db.insert_tracking_record({}, 'user')
        assert result is False

    def test_returns_false_on_db_error(self, db):
        db._tracking_exists_cache = True
        db._engine.begin.side_effect = Exception("insert error")
        result = db.insert_tracking_record({'code': 'R100'}, 'user')
        assert result is False


class TestUpdateTrackingRecord:
    def test_updates_tracked_columns(self, db):
        db._tracking_exists_cache = True
        conn = db._engine.begin.return_value.__enter__.return_value

        result = db.update_tracking_record('R100', {'sku_group_id': 'AB2'})
        assert result is True
        conn.execute.assert_called_once()

    def test_ignores_non_tracked_columns(self, db):
        db._tracking_exists_cache = True
        result = db.update_tracking_record('R100', {'description': 'foo'})
        assert result is False

    def test_skips_when_table_missing(self, db):
        conn = db._engine.connect.return_value.__enter__.return_value
        conn.execute.return_value.fetchone.return_value = None
        result = db.update_tracking_record('R100', {'sku_group_id': 'AB2'})
        assert result is False


class TestGetAllAllocatedIds:
    def test_returns_ids_from_tracking_table(self, db):
        db._tracking_exists_cache = True
        conn = db._engine.connect.return_value.__enter__.return_value
        conn.execute.return_value.fetchall.return_value = [('AA1',), ('AB2',), ('AC3',)]

        result = db.get_all_allocated_ids('sku_group_id')
        assert result == {'AA1', 'AB2', 'AC3'}

    def test_falls_back_to_live_table_when_tracking_missing(self, db):
        # First call to _tracking_table_exists returns False
        conn = db._engine.connect.return_value.__enter__.return_value
        conn.execute.return_value.fetchone.return_value = None
        conn.execute.return_value.fetchall.return_value = [('AA1',)]

        result = db.get_all_allocated_ids('sku_group_id')
        # Should still return data from fallback query
        assert isinstance(result, set)

    def test_returns_empty_on_error(self, db):
        db._tracking_exists_cache = True
        db._engine.connect.side_effect = Exception("query error")
        result = db.get_all_allocated_ids('sku_group_id')
        assert result == set()

    def test_strips_and_uppercases_values(self, db):
        db._tracking_exists_cache = True
        conn = db._engine.connect.return_value.__enter__.return_value
        conn.execute.return_value.fetchall.return_value = [(' aa1 ',), ('Ab2',)]

        result = db.get_all_allocated_ids('sku_group_id')
        assert result == {'AA1', 'AB2'}

    def test_filters_empty_values(self, db):
        db._tracking_exists_cache = True
        conn = db._engine.connect.return_value.__enter__.return_value
        conn.execute.return_value.fetchall.return_value = [('AA1',), ('',), (None,)]

        result = db.get_all_allocated_ids('sku_group_id')
        assert result == {'AA1'}


class TestGetAllAllocatedIdsMulti:
    def test_unions_across_columns(self, db):
        db._tracking_exists_cache = True
        conn = db._engine.connect.return_value.__enter__.return_value
        # Each call to get_all_allocated_ids queries DB
        conn.execute.return_value.fetchall.side_effect = [
            [('A01',)],  # mk_mdl_grp_tier_1
            [('A02',)],  # mk_mdl_grp_tier_2
            [('A01',)],  # mk_mdl_grp_tier_3 (duplicate)
            [],           # mk_mdl_grp_tier_4
        ]
        result = db.get_all_allocated_ids_multi([
            'mk_mdl_grp_tier_1', 'mk_mdl_grp_tier_2',
            'mk_mdl_grp_tier_3', 'mk_mdl_grp_tier_4'
        ])
        assert 'A01' in result
        assert 'A02' in result
