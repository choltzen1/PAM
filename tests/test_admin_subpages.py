import os, sys, importlib.util, pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

spec = importlib.util.spec_from_file_location('app', os.path.join(project_root,'app.py'))
if spec and spec.loader:
    module = importlib.util.module_from_spec(spec)
    sys.modules['app'] = module
    spec.loader.exec_module(module)  # type: ignore
    app = module.app
else:
    raise RuntimeError('Failed to load app module')

@pytest.fixture(scope='module')
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

@pytest.mark.parametrize('path', ['/admin/data','/admin/performance','/admin/integrations','/admin/security'])
def test_subpages_load(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True).lower()
    assert 'admin-subpage' in body
