import os
import sys
import importlib.util
import pytest
from sqlalchemy.engine import Connection
import requests

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


def pytest_sessionstart(session):
    if session.config.getoption("--run-integration"):
        return
    if os.getenv("PYTEST_ALLOW_PROD_DB") == "1":
        return

    server = (os.getenv("PAM_DB_SERVER") or "").strip().lower()
    if not server:
        return

    prod_like_markers = ("prod", "prd", "production")
    local_markers = ("localhost", "127.0.0.1", ".local")
    if any(m in server for m in prod_like_markers) and not any(m in server for m in local_markers):
        raise pytest.UsageError(
            "Refusing to run default tests with prod-like PAM_DB_SERVER. "
            "Use a non-prod DB, or set PYTEST_ALLOW_PROD_DB=1 explicitly, "
            "or run only marked integration tests with --run-integration."
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


@pytest.fixture(autouse=True)
def block_external_http(monkeypatch, request):
    """Block outbound HTTP(S) in normal test runs to prevent external side effects."""
    if "integration" in request.keywords and request.config.getoption("--run-integration"):
        return

    original_request = requests.sessions.Session.request

    def guarded_request(self, method, url, *args, **kwargs):
        url_text = str(url or "")
        lowered = url_text.lower()
        allowed_prefixes = (
            "http://127.0.0.1",
            "http://localhost",
            "https://127.0.0.1",
            "https://localhost",
        )
        if lowered.startswith(("http://", "https://")) and not lowered.startswith(allowed_prefixes):
            raise AssertionError(
                f"Blocked outbound HTTP during test run: {url_text}. "
                "Mock network calls, or mark test @pytest.mark.integration and run with --run-integration."
            )
        return original_request(self, method, url, *args, **kwargs)

    monkeypatch.setattr(requests.sessions.Session, "request", guarded_request)
