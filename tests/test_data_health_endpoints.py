import os, sys, importlib.util
import pytest

# Force fake DB mode (if code later checks this) - placeholder
os.environ.setdefault('PAM_TEST_FAKE_DB','1')

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
app_path = os.path.join(project_root, 'app.py')

spec = importlib.util.spec_from_file_location('app', app_path)
if spec and spec.loader:
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

def test_pcr_stats_endpoint(client):
    resp = client.get('/admin/pcr-stats')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert 'success' in data

def test_date_diagnostics_endpoint(client):
    resp = client.get('/admin/date-diagnostics')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'success' in data


def test_data_health_endpoint(client):
    resp = client.get('/admin/data-health')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'success' in data
