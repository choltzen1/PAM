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


def test_get_promo_details_after_insert(client):
    # Insert promo via data manager then verify endpoint reflects it
    promo_code = 'API999'
    factory.data_manager.save_promo(promo_code, {
        'owner':'Unit','description':'Unit Test','bill_facing_name':'UT','orbit_id':'ORBIT-UNIT'
    }, user_name='Test')
    r = client.get(f'/api/get_promo_details/{promo_code}')
    assert r.status_code == 200
    js = r.get_json()
    assert js['found'] is True
    assert js['promo_code'] == promo_code


def test_search_orbit_found(client):
    code = 'ORBITX'
    factory.data_manager.save_promo(code, {
        'owner':'Orbit','description':'Orbit Promo','bill_facing_name':'Orbit Name','orbit_id':'ORB-XYZ'
    }, user_name='Test')
    r = client.get('/api/search_orbit/ORB-XYZ')
    assert r.status_code == 200
    js = r.get_json()
    assert js['found'] is True
    assert js['promo_code'] == code


def test_search_orbit_not_found(client):
    r = client.get('/api/search_orbit/NOT-REAL-123')
    assert r.status_code == 200
    js = r.get_json()
    assert js['found'] is False


def test_update_testing_status_success(client):
    code = 'TESTSTS'
    factory.data_manager.save_promo(code, {'owner':'STS'}, user_name='Test')
    r = client.post('/api/update_testing_status', json={'promo_code':code,'test_type':'functional','status':'Passed'})
    assert r.status_code == 200
    js = r.get_json()
    assert js['success'] is True
    updated = factory.data_manager.get_promo(code)
    assert updated.get('test_status') == 'Passed'


def test_update_testing_status_invalid_type(client):
    code = 'BADTYPE'
    factory.data_manager.save_promo(code, {'owner':'STS'}, user_name='Test')
    r = client.post('/api/update_testing_status', json={'promo_code':code,'test_type':'weird','status':'X'})
    assert r.status_code == 400
    js = r.get_json()
    assert js['success'] is False


def test_update_testing_status_not_found(client):
    r = client.post('/api/update_testing_status', json={'promo_code':'MISSING','test_type':'functional','status':'Fail'})
    assert r.status_code == 404
    js = r.get_json()
    assert js['success'] is False
