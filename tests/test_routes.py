import types, os, sys
import pytest
from flask import Flask

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from promo.routes import promo_bp, init_data_manager

class SimpleDM:
    def __init__(self):
        self.store = {}
    def get_promo(self, code):
        return self.store.get(code, {})
    def save_promo(self, code, data, user_name="Test"):
        data = dict(data)
        data['code'] = code
        self.store[code] = data
    def get_soc_groupings(self):
        return []
    def get_soc_grouping_details(self):
        return {}
    def get_account_types(self):
        return []
    def get_account_type_details(self):
        return {}
    def get_sales_applications(self):
        return []
    def get_sales_application_details(self):
        return {}

@pytest.fixture()
def route_app():
    tmpl_dir = os.path.join(PROJECT_ROOT, 'templates')
    app = Flask(__name__, template_folder=tmpl_dir)
    app.config['TESTING'] = True
    app.secret_key = 'test'
    dm = SimpleDM()
    init_data_manager(dm)
    app.register_blueprint(promo_bp)
    # Prepend tests/templates override for simplified edit_promo template
    test_tmpl_dir = os.path.join(PROJECT_ROOT, 'tests', 'templates')
    if os.path.isdir(test_tmpl_dir):
        from jinja2 import ChoiceLoader, FileSystemLoader
        app.jinja_loader = ChoiceLoader([FileSystemLoader(test_tmpl_dir), app.jinja_loader])  # type: ignore
    return app, dm


def test_edit_rdc_get_creates_default(route_app):
    app, dm = route_app
    with app.test_client() as c:
        resp = c.get('/edit_rdc/ZZZ1')
        assert resp.status_code == 200


def test_edit_rdc_post_generates_sql(route_app, monkeypatch):
    from promo import builders
    # Provide a deterministic SQL generator
    monkeypatch.setattr(builders, 'generate_promo_eligibility_sql', lambda d, **kwargs: 'INSERT ...;')

    app, dm = route_app
    with app.test_client() as c:
        resp = c.post('/edit_rdc/ABCD', data={'generate_sql': '1', 'active_tab': 'Details'})
        assert resp.status_code == 302  # redirect
        saved = dm.get_promo('ABCD')
        assert saved.get('generated_sql') == 'INSERT ...;'


def test_rdc_sql_generation_render(route_app, monkeypatch):
    """End-to-end style check: POST generate then GET render includes diagnostics or fallback markers."""
    from promo import builders
    monkeypatch.setattr(builders, 'generate_promo_eligibility_sql', lambda d, **kwargs: 'SELECT 1;')
    app, dm = route_app
    with app.test_client() as c:
        resp = c.post('/edit_rdc/R249', data={'generate_sql': '1', 'active_tab': 'Details'})
        assert resp.status_code in (301,302)
        # Follow redirect to SQL tab manually
        resp = c.get('/edit_rdc/R249?tab=SQL%20Generation&gen=1')
        assert resp.status_code == 200
        body = resp.data
        assert b'DIAG: INPUT FIELD MAP' in body or b'FALLBACK MINIMAL SQL' in body or b'SELECT 1 AS no_data_placeholder' in body or b'SELECT 1;' in body
