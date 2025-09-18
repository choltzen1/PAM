import os
import sys
import importlib.util
import pytest

# Dynamic import for app to handle path issues during pytest
if 'app' in sys.modules:
    _app_module = sys.modules['app']
else:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    app_path = os.path.join(project_root, 'app.py')
    spec = importlib.util.spec_from_file_location('app', app_path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules['app'] = module
        spec.loader.exec_module(module)  # type: ignore
        _app_module = module
    else:
        raise RuntimeError('Failed to load app module spec in conftest')

flask_app = _app_module.app

@pytest.fixture(scope='session')
def app():
    flask_app.config['TESTING'] = True
    return flask_app

@pytest.fixture()
def client(app):
    with app.test_client() as c:
        yield c
