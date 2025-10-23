import os

def test_orbit_search_start_date_alias(monkeypatch):
    from data.orbit_database import OrbitDatabaseManager

    class FakeCursor:
        def __init__(self):
            self.description = [
                ('Owner', None, None, None, None, None, None),
                ('bill_facing_name', None, None, None, None, None, None),
                ('orbit_id', None, None, None, None, None, None),
                ('description', None, None, None, None, None, None),
                ('promo_start_date', None, None, None, None, None, None),
                ('promo_end_date', None, None, None, None, None, None),
            ]
            self._row = [
                'OwnerX', 'Bill Name', '12345', 'A desc', '2025-09-01', '2025-09-30'
            ]
        def execute(self, sql, params):
            assert 'promo_srart_date AS promo_start_date' in sql
            assert params == ('12345',)
        def fetchone(self):
            return self._row

    class FakeConnection:
        def cursor(self):
            return FakeCursor()
        def close(self):
            pass

    def fake_connect(self):  # self is OrbitDatabaseManager instance
        return FakeConnection()

    monkeypatch.setattr(OrbitDatabaseManager, '_connect', fake_connect)

    from services.promo_codes_service import orbit_search
    res = orbit_search('12345')
    assert res['found'] is True
    assert res['orbit_id'] == '12345'
    assert res['start_date'] == '2025-09-01'
    assert res['end_date'] == '2025-09-30'
    assert res['bill_facing_name'] == 'Bill Name'