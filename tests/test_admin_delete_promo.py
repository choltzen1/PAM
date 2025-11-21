import pytest
import factory

@pytest.fixture()
def client():
    app = factory.create_app({'TESTING': True})
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