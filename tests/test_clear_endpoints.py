import os, sys, importlib.util
import json
import pytest

pytestmark = pytest.mark.no_external_writes

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('PAM_VALIDATION_MODE','1')

spec = importlib.util.spec_from_file_location('app', os.path.join(PROJECT_ROOT,'app.py'))
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)  # type: ignore
app = module.app

_PROMO_STORE = {}


def _fake_get_promo(code):
    row = _PROMO_STORE.get(code)
    return dict(row) if row else {}


def _fake_save_promo(code, data, user_name='Test'):
    payload = dict(data or {})
    payload['code'] = code
    _PROMO_STORE[code] = payload

def seed_promo(client, code='TEST123'):
    dm = getattr(module, 'data_manager', None)
    if dm is None:
        import factory as f
        dm = getattr(f, 'data_manager', None)
    assert dm is not None, 'data_manager not initialized'
    dm.save_promo(code, {'code':code,'trade_in_group_id':'X','broken_trade':'Y','tier_1_amount':'10','segment_name':'SEG'}, user_name='Tester')
    return code

@pytest.fixture()
def client(monkeypatch):
    app.config['TESTING'] = True
    _PROMO_STORE.clear()
    dm = getattr(module, 'data_manager', None)
    if dm is None:
        import factory as f
        dm = getattr(f, 'data_manager', None)
    assert dm is not None, 'data_manager not initialized'
    monkeypatch.setattr(dm, 'get_promo', _fake_get_promo)
    monkeypatch.setattr(dm, 'save_promo', _fake_save_promo)
    with app.test_client() as c:
        yield c


@pytest.mark.parametrize('endpoint', ['promo.clear_trade_data','promo.clear_tiers_data','promo.clear_segment_data'])
def test_clear_endpoints_blueprint_direct(client, endpoint):
    code = seed_promo(client, code='BP123')
    # Build url_for dynamically via app context
    with app.test_request_context():
        from flask import url_for
        url = url_for(endpoint, promo_code=code)
    resp = client.post(url)
    assert resp.status_code == 200
    assert resp.get_json().get('success') is True
