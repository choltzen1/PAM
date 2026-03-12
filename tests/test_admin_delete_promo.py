import pytest
import factory

pytestmark = pytest.mark.no_external_writes


_PROMO_STORE = {}


def _fake_get_promo(code):
    row = _PROMO_STORE.get(code)
    return dict(row) if row else {}


def _fake_save_promo(code, data, user_name='Test'):
    payload = dict(data or {})
    payload['code'] = code
    _PROMO_STORE[code] = payload


def _fake_delete_promo(code):
    _PROMO_STORE.pop(code, None)

@pytest.fixture()
def client(monkeypatch):
    app = factory.create_app({'TESTING': True, 'WTF_CSRF_ENABLED': False})
    _PROMO_STORE.clear()
    dm = factory.data_manager
    monkeypatch.setattr(dm, 'get_promo', _fake_get_promo)
    monkeypatch.setattr(dm, 'save_promo', _fake_save_promo)
    monkeypatch.setattr(dm, 'delete_promo', _fake_delete_promo)
    if hasattr(dm, 'force_refresh'):
        monkeypatch.setattr(dm, 'force_refresh', lambda: None)
    with app.test_client() as c:
        # Save reference to the app's data manager for test access
        c.application.data_manager = factory.data_manager
        yield c

def test_admin_delete_promo_success(client):
    # Use the same data manager instance that the app uses
    dm = client.application.data_manager
    # Seed a promo directly into JSON via data_manager
    dm.save_promo('R777', {'description':'temp','orbit_id':'O-R777'}, user_name='Test')
    # Ensure exists
    assert dm.get_promo('R777')
    r = client.post('/admin/delete-promo', json={'promo_code':'R777'})
    js = r.get_json()
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {js}"
    assert js['success'] is True, f"Delete failed: {js.get('message', 'No message')}"
    # After delete, promo should not be returned (get_promo returns {})
    deleted = dm.get_promo('R777')
    assert not deleted

def test_admin_delete_promo_not_found(client):
    r = client.post('/admin/delete-promo', json={'promo_code':'ZZZ999'})
    assert r.status_code == 404
    js = r.get_json()
    assert js['success'] is False