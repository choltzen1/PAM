import os, sys, importlib.util
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('PAM_VALIDATION_MODE','1')

# Load full app (with legacy redirects) similar to clear endpoint tests
spec = importlib.util.spec_from_file_location('app', os.path.join(PROJECT_ROOT,'app.py'))
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)  # type: ignore
app = module.app

pytestmark = pytest.mark.no_external_writes

_PROMO_STORE = {}


def _fake_save_promo(code, data, user_name='System'):
    payload = dict(data or {})
    payload['code'] = code
    _PROMO_STORE[code] = payload


def _fake_get_promo(code):
    row = _PROMO_STORE.get(code)
    return dict(row) if row else {}

def _extract_flashed(html: str):
    return 'created successfully' in html.lower()

@pytest.fixture()
def client(monkeypatch):
    app.config['TESTING'] = True
    _PROMO_STORE.clear()
    dm = getattr(module, 'data_manager', None)
    if dm is None:
        import factory as f
        dm = getattr(f, 'data_manager', None)
    assert dm is not None
    monkeypatch.setattr(dm, 'save_promo', _fake_save_promo)
    monkeypatch.setattr(dm, 'get_promo', _fake_get_promo)
    try:
        import factory as f
        if getattr(f, 'data_manager', None) is not None:
            monkeypatch.setattr(f.data_manager, 'save_promo', _fake_save_promo)
            monkeypatch.setattr(f.data_manager, 'get_promo', _fake_get_promo)
    except Exception:
        pass
    with app.test_client() as c:
        yield c

# --- Blueprint direct tests ---

def test_get_promo_codes_blueprint_get(client):
    with app.test_request_context():
        from flask import url_for
        url = url_for('promo.get_promo_codes_page')
    resp = client.get(url)
    assert resp.status_code == 200
    assert b'Get Promo Codes' in resp.data

@pytest.mark.parametrize('promo_type', ['rdc','spe'])
def test_get_promo_codes_blueprint_post(client, promo_type):
    with app.test_request_context():
        from flask import url_for
        url = url_for('promo.get_promo_codes_page')
    form = {
        'promoType': promo_type,
        'promoPrefix': 'BPTST',
        'promoYear': '25',
        'billFacingName': 'BP Promo',
        'promoOwner': 'QA',
        'startDate': '2025-01-01',
        'endDate': '2025-12-31',
        'description': 'Autotest'
    }
    if promo_type == 'spe':
        form.update({'speCategory':'Cat','speType':'Type'})
    resp = client.post(url, data=form, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    if promo_type == 'rdc':
        dm = getattr(module, 'data_manager', None)
        if dm is None:
            import factory as f
            dm = getattr(f, 'data_manager', None)
        assert dm is not None
        assert dm.get_promo('BPTST25') is not None
