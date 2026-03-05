import os, sys, importlib.util
from unittest.mock import MagicMock, patch


def load_app():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    spec = importlib.util.spec_from_file_location('app', os.path.join(project_root, 'app.py'))
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore
    return module.app


app = load_app()


@patch('jira.routes.requests.post')
def test_create_jira_ticket_smoke(mock_post):
    fake_response = MagicMock()
    fake_response.status_code = 201
    fake_response.json.return_value = {'key': 'EFPE-123'}
    fake_response.text = '{"key":"EFPE-123"}'
    mock_post.return_value = fake_response

    env_overrides = {
        'DEV_MODE': 'true',
        'DEV_USER_ROLE': 'pam_admin',
        'JIRA_USERNAME': 'fake-user',
        'JIRA_API_TOKEN': 'fake-token',
        'JIRA_URL': 'https://example.atlassian.net',
        'JIRA_PROJECT': 'EFPE',
    }

    with patch.dict(os.environ, env_overrides, clear=False):
        app.config['TESTING'] = True
        with app.test_client() as c:
            resp = c.post(
                '/create_jira_ticket',
                json={'summary': 'Test Ticket', 'description': 'Smoke', 'priority': 'High'}
            )

    assert resp.status_code == 200
    data = resp.get_json() or {}
    assert data.get('success') is True
    assert data.get('ticket_key') == 'EFPE-123'

    assert mock_post.called
    mock_post.assert_called_once()
    called_url = mock_post.call_args.args[0]
    assert called_url == 'https://example.atlassian.net/rest/api/2/issue/'
