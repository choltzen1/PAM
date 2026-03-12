"""Unit tests for data/database.py utility methods (no DB connection required)."""
import pytest

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.database import DatabaseManager


@pytest.fixture
def db():
    """DatabaseManager instance with no live connection."""
    return DatabaseManager()


# ---------------------------------------------------------------------------
# _is_transient_error
# ---------------------------------------------------------------------------

class TestIsTransientError:
    def test_timeout_is_transient(self, db):
        assert db._is_transient_error(Exception("connection timeout exceeded")) is True

    def test_timed_out_is_transient(self, db):
        assert db._is_transient_error(Exception("query timed out")) is True

    def test_network_error_is_transient(self, db):
        assert db._is_transient_error(Exception("network failure")) is True

    def test_tcp_error_is_transient(self, db):
        assert db._is_transient_error(Exception("TCP provider error")) is True

    def test_communication_link_is_transient(self, db):
        assert db._is_transient_error(Exception("communication link failure")) is True

    def test_server_not_found_is_transient(self, db):
        assert db._is_transient_error(Exception("server is not found or not accessible")) is True

    def test_login_timeout_is_transient(self, db):
        assert db._is_transient_error(Exception("login timeout expired")) is True

    def test_transport_level_is_transient(self, db):
        assert db._is_transient_error(Exception("transport-level error when receiving results")) is True

    def test_syntax_error_is_not_transient(self, db):
        assert db._is_transient_error(Exception("incorrect syntax near 'foo'")) is False

    def test_permission_denied_is_not_transient(self, db):
        assert db._is_transient_error(Exception("The SELECT permission was denied")) is False

    def test_invalid_column_is_not_transient(self, db):
        assert db._is_transient_error(Exception("invalid column name 'bar'")) is False

    def test_case_insensitive(self, db):
        assert db._is_transient_error(Exception("TIMEOUT")) is True
        assert db._is_transient_error(Exception("NETWORK ERROR")) is True


# ---------------------------------------------------------------------------
# reset_engine
# ---------------------------------------------------------------------------

class TestResetEngine:
    def test_reset_without_engine_is_safe(self, db):
        assert db._engine is None
        db.reset_engine()  # should not raise
        assert db._engine is None

    def test_reset_clears_cached_engine(self, db):
        from unittest.mock import MagicMock
        mock_engine = MagicMock()
        db._engine = mock_engine
        db.reset_engine()
        mock_engine.dispose.assert_called_once()
        assert db._engine is None
