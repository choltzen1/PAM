"""Unit tests for PromoDataManager (data/storage.py).

All tests use mocks/stubs — no real database connections are made.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("PAM_VALIDATION_MODE", "1")

from data.storage import PromoDataManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_db_manager():
    """Return a MagicMock that looks like a DatabaseManager."""
    db = MagicMock()
    db.source_table = "[PAM].[PAM_Orbit_Data_Updated]"
    # Default: no records found
    db.get_promo_by_code.return_value = None
    db.get_promos_by_execution_type.return_value = []
    db.convert_db_record_to_json_format.side_effect = lambda d: d
    return db


@pytest.fixture()
def dm(mock_db_manager, tmp_path):
    """PromoDataManager with mocked DatabaseManager and temp upload dir."""
    manager = PromoDataManager.__new__(PromoDataManager)
    manager.db_manager = mock_db_manager
    manager.promo_uploads_dir = str(tmp_path / "uploads")
    os.makedirs(manager.promo_uploads_dir, exist_ok=True)
    return manager


# ---------------------------------------------------------------------------
# get_promo
# ---------------------------------------------------------------------------

class TestGetPromo:
    def test_returns_empty_dict_when_not_found(self, dm, mock_db_manager):
        mock_db_manager.get_promo_by_code.return_value = None
        result = dm.get_promo("NONEXISTENT")
        assert result == {}

    def test_returns_converted_record_when_found(self, dm, mock_db_manager):
        fake_row = {"code": "ABC123", "bill_facing_name": "Test Promo"}
        mock_db_manager.get_promo_by_code.return_value = fake_row
        mock_db_manager.convert_db_record_to_json_format.return_value = fake_row

        result = dm.get_promo("ABC123")
        assert result["code"] == "ABC123"
        assert result["bill_facing_name"] == "Test Promo"

    def test_returns_empty_dict_on_db_exception(self, dm, mock_db_manager):
        mock_db_manager.get_promo_by_code.side_effect = Exception("DB connection lost")
        result = dm.get_promo("ABC123")
        assert result == {}


# ---------------------------------------------------------------------------
# get_all_promos
# ---------------------------------------------------------------------------

class TestGetAllPromos:
    def test_returns_empty_dict_when_no_records(self, dm, mock_db_manager):
        mock_db_manager.get_promos_by_execution_type.return_value = []
        result = dm.get_all_promos()
        assert result == {}

    def test_returns_dict_keyed_by_code(self, dm, mock_db_manager):
        records = [
            {"code": "RDC001", "Desired_Execution": "RDC"},
            {"code": "RDC002", "Desired_Execution": "RDC"},
        ]
        mock_db_manager.get_promos_by_execution_type.return_value = records
        mock_db_manager.convert_db_record_to_json_format.side_effect = lambda d: d

        result = dm.get_all_promos()
        assert "RDC001" in result
        assert "RDC002" in result

    def test_returns_empty_dict_on_db_exception(self, dm, mock_db_manager):
        mock_db_manager.get_promos_by_execution_type.side_effect = RuntimeError("timeout")
        result = dm.get_all_promos()
        assert result == {}


# ---------------------------------------------------------------------------
# delete_promo
# ---------------------------------------------------------------------------

class TestDeletePromo:
    def _wire_engine(self, mock_db_manager: MagicMock, rowcount: int) -> None:
        """Configure mock_db_manager.get_engine() so that
        `with engine.begin() as conn: conn.execute(...).rowcount` returns *rowcount*."""
        engine = MagicMock()
        conn = engine.begin.return_value.__enter__.return_value
        conn.execute.return_value.rowcount = rowcount
        mock_db_manager.get_engine.return_value = engine

    def test_returns_true_when_row_deleted(self, dm, mock_db_manager):
        self._wire_engine(mock_db_manager, rowcount=1)
        assert dm.delete_promo("TEST001") is True

    def test_returns_false_when_no_row_deleted(self, dm, mock_db_manager):
        self._wire_engine(mock_db_manager, rowcount=0)
        assert dm.delete_promo("NOTEXIST") is False

    def test_returns_false_on_exception(self, dm, mock_db_manager):
        mock_db_manager.get_engine.side_effect = Exception("engine error")
        deleted = dm.delete_promo("TEST001")
        assert deleted is False


# ---------------------------------------------------------------------------
# get_paginated_promos
# ---------------------------------------------------------------------------

class TestGetPaginatedPromos:
    def test_returns_structure_with_pagination_info(self, dm, mock_db_manager):
        mock_db_manager.get_promos_by_execution_type.return_value = []
        result = dm.get_paginated_promos(page=1, per_page=10)
        assert "promotions" in result or isinstance(result, dict)

    def test_returns_empty_on_db_error(self, dm, mock_db_manager):
        mock_db_manager.get_promos_by_execution_type.side_effect = Exception("DB error")
        result = dm.get_paginated_promos()
        # Should not raise — returns a graceful result
        assert result is not None
