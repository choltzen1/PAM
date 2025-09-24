import pytest
import factory

@pytest.fixture()
def client():
    app = factory.create_app({'TESTING': True})
    with app.test_client() as c:
        yield c

def test_admin_delete_promo_success(client):
    # Seed a promo directly into JSON via data_manager
    factory.data_manager.save_promo('R777', {'description':'temp','orbit_id':'O-R777'}, user_name='Test')
    # Ensure exists
    assert factory.data_manager.get_promo('R777')
    r = client.post('/admin/delete-promo', json={'promo_code':'R777'})
    assert r.status_code == 200
    js = r.get_json()
    assert js['success'] is True
    # After delete, promo should not be returned (get_promo returns {})
    deleted = factory.data_manager.get_promo('R777')
    assert not deleted

def test_admin_delete_promo_not_found(client):
    r = client.post('/admin/delete-promo', json={'promo_code':'ZZZ999'})
    assert r.status_code == 404
    js = r.get_json()
    assert js['success'] is False