import os, sys, importlib.util
import json

def load_app():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    spec = importlib.util.spec_from_file_location('app', os.path.join(project_root,'app.py'))
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore
    return module.app

app = load_app()

def test_create_jira_ticket_smoke():
    app.config['TESTING'] = True
    with app.test_client() as c:
        resp = c.post('/create_jira_ticket', json={'summary':'Test Ticket','description':'Smoke','priority':'High'})
        # Expect either redirect then JSON or direct JSON error depending on config
        if resp.status_code == 302:
            loc = resp.headers['Location']
            resp = c.post(loc, json={'summary':'Test Ticket','description':'Smoke','priority':'High'})
        assert resp.status_code in (200,400)
        data = resp.get_json() or {}
        assert 'success' in data
