import os
import sys
import importlib.util
import pytest
from sqlalchemy.engine import Connection

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


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run tests marked as integration (may touch real external services/databases).",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    skip_integration = pytest.mark.skip(reason="integration test skipped by default; use --run-integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(autouse=True)
def block_db_writes(monkeypatch, request):
    """Block SQL writes in normal test runs to prevent accidental prod mutations."""
    if "integration" in request.keywords and request.config.getoption("--run-integration"):
        return

    original_execute = Connection.execute

    def guarded_execute(self, statement, *args, **kwargs):
        sql_text = str(getattr(statement, "text", statement)).lstrip().lower()
        blocked_prefixes = (
            "insert",
            "update",
            "delete",
            "merge",
            "create",
            "alter",
            "drop",
            "truncate",
        )
        if sql_text.startswith(blocked_prefixes):
            raise AssertionError(
                "Blocked database write during test run. "
                "Use mocks, or mark as @pytest.mark.integration and run with --run-integration."
            )
        return original_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(Connection, "execute", guarded_execute)
