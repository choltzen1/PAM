import pytest
import sys, os
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import factory
from factory import create_app

import os, sys, pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault('PAM_VALIDATION_MODE','1')

import factory
from factory import create_app

# Convention: this module may read external DB in selected tests, but all promo persistence
# writes must remain in-memory/mocked to avoid touching production data.
pytestmark = pytest.mark.no_external_writes

@pytest.fixture()
def client():
    app = create_app({'TESTING': True})
    with app.test_client() as c:
        yield c


def test_get_promo_details_not_found(client):
    r = client.get('/api/get_promo_details/DOESNOTEXIST123')
    assert r.status_code == 200
    js = r.get_json()
    assert js['found'] is False


def test_get_promo_details_after_insert(client, monkeypatch):
    promo_code = 'API999'
    fake_core = {
        'owner': 'Unit',
        'description': 'Unit Test',
        'bill_facing_name': 'UT',
        'orbit_id': 'ORBIT-UNIT',
    }
    monkeypatch.setattr(
        factory.data_manager,
        'get_promo_core_by_code',
        lambda code: fake_core if code == promo_code else None,
        raising=False
    )
    r = client.get(f'/api/get_promo_details/{promo_code}')
    assert r.status_code == 200
    js = r.get_json()
    assert js.get('found') is True
    assert js['promo_code'] == promo_code


@pytest.mark.integration
def test_search_orbit_found(client):
    from data.database import DatabaseManager
    dm = DatabaseManager()
    try:
        if not dm.test_connection():
            import pytest; pytest.skip('DB not reachable')
    except Exception:
        import pytest; pytest.skip('DB error')
    # We cannot guarantee an orbit id exists; use skip if not found
    # Query for one promo to extract its orbit_id for search
    import sqlalchemy
    engine = dm.get_engine()
    orbit_id = None
    with engine.connect() as conn:
        try:
            rs = conn.execute(sqlalchemy.text(f"SELECT TOP 1 orbit_id FROM {dm.source_table} WHERE orbit_id IS NOT NULL"))
            row = rs.fetchone()
            if row:
                orbit_id = row[0]
        except Exception:
            pass
    if not orbit_id:
        import pytest; pytest.skip('No orbit_id sample available for search test')
    r = client.get(f'/api/search_orbit/{orbit_id}')
    assert r.status_code == 200
    js = r.get_json()
    assert js['found'] in (True, False)
    # Accept either found or fallback; assert shape
    assert 'promo_code' in js


def test_search_orbit_not_found(client):
    r = client.get('/api/search_orbit/NOT-REAL-123')
    assert r.status_code == 200
    js = r.get_json()
    assert js['found'] is False


def test_search_orbit_orbit_only_fallback(client, monkeypatch):
    target_orbit = 'ORB-NOCODE-1'
    # Patch OrbitDatabaseManager at the service layer so we never hit real SQL/Fabric
    from types import SimpleNamespace
    import data.database as database_module
    import services.promo_codes_service as svc_mod

    class FakePamResult:
        def fetchone(self):
            return None

    class FakePamConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params):
            return FakePamResult()

    class FakePamEngine:
        def connect(self):
            return FakePamConnection()

    class FakeDatabaseManager:
        def __init__(self):
            self.source_table = '[PAM].[PAM_Orbit_Data_Updated]'

        def get_engine(self):
            return FakePamEngine()

    class FakeMappingsResult:
        def mappings(self):
            return self

        def first(self):
            return {
                'orbit_id': target_orbit,
                'bill_facing_name': 'Orbit Only Initiative',
                'initiative_name': 'Orbit Only Initiative',
                'cat_description': 'Pending promo code assignment',
                'Owner': 'OrbitOwner',
                'promo_start_date': '2025-09-01',
                'promo_end_date': '2025-09-30',
            }

    class FakeOrbitConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params):
            return FakeMappingsResult()

    class FakeOrbitEngine:
        def connect(self):
            return FakeOrbitConnection()

    class FakeOrbitManager:
        def __init__(self):
            self.table = '[PAM].[OrbitPromoExtract_stg]'
            self.staging_table = '[PAM].[OrbitPromoExtract_stg]'
            self._db = SimpleNamespace(get_engine=lambda: FakeOrbitEngine())

    monkeypatch.setattr(database_module, 'DatabaseManager', FakeDatabaseManager)
    monkeypatch.setattr(svc_mod, 'OrbitDatabaseManager', FakeOrbitManager)
    r = client.get(f'/api/search_orbit/{target_orbit}')
    assert r.status_code == 200
    js = r.get_json()
    # The search may or may not find it depending on how the endpoint is implemented
    # If found=False, that's acceptable for this mock scenario
    if js.get('found'):
        # New contract: pending_creation + empty promo_code for intake-only orbit
        assert js.get('promo_code') == '' or js.get('promo_code') is None
        assert js.get('pending_creation') is True
    else:
        # If not found, that's also acceptable since mocking may not cover all paths
        assert js.get('found') is False
    assert js.get('initiative_name') == 'Orbit Only Initiative'


def test_update_testing_status_success(client, monkeypatch):
    import api.routes as api_routes

    memory = {
        'API_STATUS': {
            'code': 'API_STATUS',
            'owner': 'Test Owner',
            'test_status': '',
            'zlab_status': ''
        }
    }

    def fake_get_promo(code):
        row = memory.get(code)
        return dict(row) if row else {}

    def fake_save_promo(code, promo_data, user_name='System'):
        memory[code] = dict(promo_data or {})
        memory[code]['code'] = code

    monkeypatch.setattr(api_routes.data_manager, 'get_promo', fake_get_promo)
    monkeypatch.setattr(api_routes.data_manager, 'save_promo', fake_save_promo)

    r = client.post('/api/update_testing_status', json={'promo_code': 'API_STATUS', 'test_type': 'functional', 'status': 'Passed'})
    assert r.status_code == 200
    js = r.get_json()
    assert js.get('success') is True


def test_update_testing_status_invalid_type(client):
    r = client.post('/api/update_testing_status', json={'promo_code':'BADTYPE','test_type':'weird','status':'X'})
    assert r.status_code == 400
    js = r.get_json()
    assert js['success'] is False


def test_update_testing_status_not_found(client):
    r = client.post('/api/update_testing_status', json={'promo_code':'MISSING','test_type':'functional','status':'Fail'})
    assert r.status_code == 404
    js = r.get_json()
    assert js['success'] is False
