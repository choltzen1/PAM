from types import SimpleNamespace


def test_orbit_search_uses_sql_tracking_then_staging(monkeypatch):
    import data.database as database_module
    import services.promo_codes_service as promo_codes_service

    calls = []

    class FakePamResult:
        def fetchone(self):
            return None

    class FakePamConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params):
            sql_text = str(sql)
            calls.append(('pam', sql_text, params))
            assert '[PAM].[PAM_Orbit_Data_Updated]' in sql_text
            assert params == {'oid': '12345'}
            return FakePamResult()

    class FakePamEngine:
        def connect(self):
            return FakePamConnection()

    class FakeMappingsResult:
        def mappings(self):
            return self

        def first(self):
            return {
                'Owner': 'OwnerX',
                'bill_facing_name': 'Bill Name',
                'orbit_id': '12345',
                'initiative_name': 'Initiative',
                'cat_description': 'A desc',
                'promo_start_date': '2025-09-01',
                'promo_end_date': '2025-09-30',
            }

    class FakeOrbitConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params):
            sql_text = str(sql)
            calls.append(('staging', sql_text, params))
            assert '[PAM].[OrbitPromoExtract_stg]' in sql_text
            assert params == {'oid': '12345'}
            return FakeMappingsResult()

    class FakeOrbitEngine:
        def connect(self):
            return FakeOrbitConnection()

    class FakeDatabaseManager:
        def __init__(self):
            self.source_table = '[PAM].[PAM_Orbit_Data_Updated]'

        def get_engine(self):
            return FakePamEngine()

    class FakeOrbitDatabaseManager:
        def __init__(self):
            self.staging_table = '[PAM].[OrbitPromoExtract_stg]'
            self._db = SimpleNamespace(get_engine=lambda: FakeOrbitEngine())

    monkeypatch.setattr(database_module, 'DatabaseManager', FakeDatabaseManager)
    monkeypatch.setattr(promo_codes_service, 'OrbitDatabaseManager', FakeOrbitDatabaseManager)

    res = promo_codes_service.orbit_search('12345')

    assert calls[0][0] == 'pam'
    assert calls[1][0] == 'staging'
    assert res['found'] is True
    assert res['already_generated'] is False
    assert res['orbit_id'] == '12345'
    assert res['start_date'] == '2025-09-01'
    assert res['end_date'] == '2025-09-30'
    assert res['bill_facing_name'] == 'Bill Name'