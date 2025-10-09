import pytest
import factory
import os

class DummyDB:
    def __init__(self, record=None):
        self.record = record or {
            'orbit_id': '12345',
            'description': 'A test promo',
            'bill_facing_name': 'Bill Name'
        }
    def get_full_orbit_record_by_orbit_id(self, oid):
        if self.record and self.record.get('orbit_id') == oid:
            return self.record
        return None
    def convert_db_record_to_json_format(self, rec):
        return dict(rec)
    def get_promos_by_execution_type(self, exec_type):
        return []
    def get_highest_sequential_promo_code(self):
        return None
    # Stubs for save_promo dependency chain
    def update_promo_fields(self, code, field_map):
        return True
    def upsert_promo_extras(self, code, extras, user):
        return True
    def record_creation_event(self, code, inserted_fields, user='System'):
        return True
    def record_update_event(self, code, diff, user='System', window_seconds=60):
        return True

@pytest.fixture()
def client(monkeypatch):
    os.environ.setdefault('PAM_VALIDATION_MODE','1')
    # Patch DatabaseManager class before app creation so route instantiation uses dummy
    from data import database
    monkeypatch.setattr(database, 'DatabaseManager', lambda: DummyDB())
    app = factory.create_app({'TESTING': True})
    with app.test_client() as c:
        yield c

def test_generate_and_ingest_success(client):
    r = client.post('/api/generate_and_ingest', json={'orbit_id': '12345'})
    assert r.status_code == 200
    js = r.get_json()
    assert js['success'] is True
    assert js['orbit_id'] == '12345'
    assert js['promo_code'].startswith('R') or js['promo_code'].startswith('A')  # depending on existing data

@pytest.fixture()
def client_not_found(monkeypatch):
    os.environ.setdefault('PAM_VALIDATION_MODE','1')
    from data import database
    class NF:
        def get_full_orbit_record_by_orbit_id(self, oid):
            return None
        def convert_db_record_to_json_format(self, rec):
            return dict(rec)
        def get_promos_by_execution_type(self, exec_type):
            return []
        def get_highest_sequential_promo_code(self):
            return None
    monkeypatch.setattr(database, 'DatabaseManager', NF)
    app = factory.create_app({'TESTING': True})
    with app.test_client() as c:
        yield c


def test_generate_and_ingest_not_found(client_not_found):
    r = client_not_found.post('/api/generate_and_ingest', json={'orbit_id': '99999'})
    assert r.status_code == 404
    js = r.get_json()
    assert js['success'] is False


def test_generate_and_ingest_conflict(client, monkeypatch):
    # First create
    first = client.post('/api/generate_and_ingest', json={'orbit_id': '12345'})
    assert first.status_code == 200
    created_code = first.get_json()['promo_code']
    # Monkeypatch get_all_promos to reflect newly created promo with orbit mapping for conflict detection
    import factory as _factory
    def fake_all():
        return {created_code: {'orbit_id': '12345'}}
    monkeypatch.setattr(_factory.data_manager, 'get_all_promos', fake_all)
    # Second attempt with same orbit id should 409
    second = client.post('/api/generate_and_ingest', json={'orbit_id': '12345'})
    assert second.status_code == 409
    js = second.get_json()
    assert js['success'] is False
    assert 'existing_code' in js
