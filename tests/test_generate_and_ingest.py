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

@pytest.fixture()
def client(monkeypatch):
    os.environ.setdefault('PAM_VALIDATION_MODE','1')
    app = factory.create_app({'TESTING': True})
    # Patch DatabaseManager used inside endpoint
    from data import database
    monkeypatch.setattr(database, 'DatabaseManager', lambda: DummyDB())
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
    app = factory.create_app({'TESTING': True})
    from data import database
    # DB returns None for any id
    class NF:
        def get_full_orbit_record_by_orbit_id(self, oid):
            return None
        def convert_db_record_to_json_format(self, rec):
            return dict(rec)
    monkeypatch.setattr(database, 'DatabaseManager', NF)
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
