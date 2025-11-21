import pytest
import importlib.util
import os
import sys

# Attempt to import app module robustly for Windows test execution
if 'app' in sys.modules:
    _app_mod = sys.modules['app']
    if hasattr(_app_mod, 'app'):
        app = getattr(_app_mod, 'app')  # Flask instance
    else:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        app_path = os.path.join(project_root, 'app.py')
        spec = importlib.util.spec_from_file_location('app', app_path)
        if not spec or not spec.loader:
            raise RuntimeError('Failed to load Flask app for tests')
        module = importlib.util.module_from_spec(spec)
        sys.modules['app'] = module
        spec.loader.exec_module(module)  # type: ignore
        app = module.app
else:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    app_path = os.path.join(project_root, 'app.py')
    spec = importlib.util.spec_from_file_location('app', app_path)
    if not spec or not spec.loader:
        raise RuntimeError('Failed to load Flask app for tests (cold load)')
    module = importlib.util.module_from_spec(spec)
    sys.modules['app'] = module
    spec.loader.exec_module(module)  # type: ignore
    app = module.app

# Basic markers expected in templates to confirm correct page render
PAGE_MARKERS = {
    '/rdc': 'RDC',
    '/spe': 'SPE',
    '/rebates': 'Rebates',
    '/date-mismatch': 'Date Mismatch',
    '/get-promo-codes': 'Get Promo Codes',
    '/approvers': 'Approvers',
    '/reviewers': 'Reviewers',
    '/links': 'Links',
    '/updates': 'Updates',
    '/capacity': 'Capacity',
    '/test-page': 'Test',
    '/admin': 'Admin'
}

@pytest.fixture(scope='module')
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

@pytest.mark.parametrize('path,marker', list(PAGE_MARKERS.items()))
def test_nav_pages(client, path, marker):
    resp = client.get(path)
    assert resp.status_code == 200
    assert marker.lower() in resp.get_data(as_text=True).lower()

