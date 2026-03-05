import types
import pandas as pd
import pytest
from data.database import DatabaseManager

pytestmark = pytest.mark.no_external_writes

class FakeEngine:
    def connect(self):
        class Ctx:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def execute(self, *a, **k):
                return [(1,)]
        return Ctx()

def test_get_recent_promos_injects_diagnostics(monkeypatch):
    dm = DatabaseManager()
    # Prevent real engine creation
    monkeypatch.setattr(dm, 'get_engine', lambda: FakeEngine())

    # Mock get_dataframe behavior based on SQL content
    def fake_get_dataframe(sql_text, params=None):
        sql_string = str(sql_text)
        if 'SELECT promo_start_date FROM' in sql_string:
            # Raw date values including invalid entries
            return pd.DataFrame({'promo_start_date': [
                '01/15/2025',  # valid m/d/Y
                '2025-02-01',  # valid ISO
                '13/40/2025',  # invalid
                'abc',         # invalid
                '',            # invalid empty
                None           # invalid None
            ]})
        else:
            # Main filtered query should only include valid rows (first two)
            return pd.DataFrame([
                {
                    'code': 'P001', 'Owner': 'Alice', 'description': 'Promo 1',
                    'promo_start_date': '01/15/2025', 'promo_end_date': '02/01/2025',
                    'amount': 10, 'operator_id': 'OP1', 'orbit_id': 'ORB1'
                },
                {
                    'code': 'P002', 'Owner': 'Bob', 'description': 'Promo 2',
                    'promo_start_date': '2025-02-01', 'promo_end_date': '2025-03-01',
                    'amount': 20, 'operator_id': 'OP2', 'orbit_id': 'ORB2'
                }
            ])

    monkeypatch.setattr(dm, 'get_dataframe', fake_get_dataframe)

    records = dm.get_recent_promos(days=7)
    assert len(records) == 2
    diag = records[0].get('_date_diagnostics')
    assert diag is not None, 'Diagnostics dict missing'
    assert diag['total_with_value'] == 6
    assert diag['valid_dates'] == 2
    assert diag['invalid_dates'] == 4
    assert diag['days_window'] == 7
