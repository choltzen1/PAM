import os
import pytest
import importlib.util
import sys

# Robust import of app
if 'app' in sys.modules:
    app = sys.modules['app']
else:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    app_path = os.path.join(project_root, 'app.py')
    spec = importlib.util.spec_from_file_location('app', app_path)
    if spec and spec.loader:  # runtime safety
        module = importlib.util.module_from_spec(spec)
        sys.modules['app'] = module
        spec.loader.exec_module(module)  # type: ignore
        app = module.app
    else:
        raise RuntimeError('Failed to load app module spec for tests')

@pytest.fixture(scope='module')
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

def test_admin_dashboard_page(client):
    resp = client.get('/admin')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Promotions Count'.lower().split()[0] in body.lower() or 'Admin'.lower() in body.lower()

def test_admin_stats_endpoint(client):
    resp = client.get('/admin/stats')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get('success') is True
    assert 'stats' in data


def test_version_history_page(client):
    resp = client.get('/version-history')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Version History'.lower() in body.lower()
