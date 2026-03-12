"""Unit tests for auth.py: role hierarchy, decorators, owner matching, user name extraction."""
import base64
import json
import pytest
from unittest.mock import patch

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auth import (
    has_role,
    get_user_roles_from_azure_roles,
    can_edit_promo,
    get_current_user_name,
    ROLE_HIERARCHY,
)


# ---------------------------------------------------------------------------
# has_role
# ---------------------------------------------------------------------------

def _user(roles):
    return {'name': 'Test User', 'email': 'test@example.com', 'id': 'u1', 'roles': roles}


class TestHasRole:
    def test_none_user_returns_false(self):
        assert has_role(None, 'pam_users') is False

    def test_exact_role_match(self):
        assert has_role(_user(['pam_users']), 'pam_users') is True

    def test_role_not_granted(self):
        assert has_role(_user(['pam_viewonly']), 'pam_users') is False

    def test_admin_inherits_all_roles(self):
        u = _user(['pam_admin'])
        for role in ROLE_HIERARCHY['pam_admin']:
            assert has_role(u, role) is True, f"pam_admin should inherit {role}"

    def test_pam_users_inherits_viewonly_and_research(self):
        u = _user(['pam_users'])
        assert has_role(u, 'pam_viewonly') is True
        assert has_role(u, 'pam_research') is True

    def test_pam_users_does_not_inherit_admin(self):
        assert has_role(_user(['pam_users']), 'pam_admin') is False

    def test_approver_inherits_viewonly(self):
        assert has_role(_user(['pam_approvers']), 'pam_viewonly') is True

    def test_approver_does_not_inherit_users(self):
        assert has_role(_user(['pam_approvers']), 'pam_users') is False

    def test_research_only_no_edit_access(self):
        u = _user(['pam_research'])
        assert has_role(u, 'pam_users') is False
        assert has_role(u, 'pam_admin') is False

    def test_multiple_roles_combined(self):
        u = _user(['pam_viewonly', 'pam_research'])
        assert has_role(u, 'pam_research') is True
        assert has_role(u, 'pam_users') is False

    def test_empty_roles(self):
        assert has_role(_user([]), 'pam_viewonly') is False


# ---------------------------------------------------------------------------
# get_user_roles_from_azure_roles
# ---------------------------------------------------------------------------

class TestGetUserRolesFromAzureRoles:
    def test_admin_maps_correctly(self):
        assert get_user_roles_from_azure_roles(['Admin']) == ['pam_admin']

    def test_user_maps_correctly(self):
        assert get_user_roles_from_azure_roles(['User']) == ['pam_users']

    def test_unknown_role_defaults_to_viewonly(self):
        roles = get_user_roles_from_azure_roles(['UnknownRole'])
        assert roles == ['pam_viewonly']

    def test_empty_list_defaults_to_viewonly(self):
        roles = get_user_roles_from_azure_roles([])
        assert roles == ['pam_viewonly']

    def test_multiple_azure_roles(self):
        roles = get_user_roles_from_azure_roles(['Admin', 'Approver'])
        assert 'pam_admin' in roles
        assert 'pam_approvers' in roles

    def test_all_known_roles_map(self):
        from auth import AZURE_ROLE_MAPPING
        for azure_name, internal_name in AZURE_ROLE_MAPPING.items():
            result = get_user_roles_from_azure_roles([azure_name])
            assert internal_name in result


# ---------------------------------------------------------------------------
# can_edit_promo (needs Flask app context for g)
# ---------------------------------------------------------------------------

class TestCanEditPromo:
    def test_no_user_returns_false(self, app):
        with app.test_request_context('/'):
            with patch('auth.get_current_user', return_value=None):
                assert can_edit_promo() is False

    def test_admin_can_edit_any_promo(self, app):
        u = _user(['pam_admin'])
        with app.test_request_context('/'):
            with patch('auth.get_current_user', return_value=u):
                assert can_edit_promo('Someone Else') is True

    def test_pam_user_can_edit_own_promo_by_email(self, app):
        u = {**_user(['pam_users']), 'email': 'john@example.com', 'name': 'John Smith'}
        with app.test_request_context('/'):
            with patch('auth.get_current_user', return_value=u):
                assert can_edit_promo('john@example.com') is True

    def test_pam_user_can_edit_own_promo_by_name(self, app):
        u = {**_user(['pam_users']), 'email': 'jsmith@example.com', 'name': 'John Smith'}
        with app.test_request_context('/'):
            with patch('auth.get_current_user', return_value=u):
                assert can_edit_promo('John Smith') is True

    def test_pam_user_cannot_edit_someone_elses_promo(self, app):
        u = {**_user(['pam_users']), 'email': 'alice@example.com', 'name': 'Alice'}
        with app.test_request_context('/'):
            with patch('auth.get_current_user', return_value=u):
                assert can_edit_promo('Bob Jones') is False

    def test_pam_user_with_no_owner_specified_can_edit(self, app):
        u = _user(['pam_users'])
        with app.test_request_context('/'):
            with patch('auth.get_current_user', return_value=u):
                assert can_edit_promo(None) is True

    def test_viewonly_cannot_edit(self, app):
        u = _user(['pam_viewonly'])
        with app.test_request_context('/'):
            with patch('auth.get_current_user', return_value=u):
                assert can_edit_promo() is False


# ---------------------------------------------------------------------------
# get_current_user_name (needs Flask request context)
# ---------------------------------------------------------------------------

def _make_principal(given=None, surname=None, name=None, preferred_username=None):
    """Build a base64-encoded X-MS-CLIENT-PRINCIPAL header payload."""
    claims = []
    if given:
        claims.append({'typ': 'givenname', 'val': given})
    if surname:
        claims.append({'typ': 'surname', 'val': surname})
    if name:
        claims.append({'typ': 'name', 'val': name})
    if preferred_username:
        claims.append({'typ': 'preferred_username', 'val': preferred_username})
    payload = json.dumps({'claims': claims})
    return base64.b64encode(payload.encode()).decode()


class TestGetCurrentUserName:
    def test_returns_none_with_no_headers(self, app):
        with app.test_request_context('/'):
            assert get_current_user_name() is None

    def test_prefers_givenname_plus_surname(self, app):
        header = _make_principal(given='Jane', surname='Doe', name='Fallback Name')
        with app.test_request_context('/', headers={'X-MS-CLIENT-PRINCIPAL': header}):
            assert get_current_user_name() == 'Jane Doe'

    def test_falls_back_to_name_claim(self, app):
        header = _make_principal(name='Jane Doe')
        with app.test_request_context('/', headers={'X-MS-CLIENT-PRINCIPAL': header}):
            assert get_current_user_name() == 'Jane Doe'

    def test_falls_back_to_preferred_username(self, app):
        header = _make_principal(preferred_username='jane@example.com')
        with app.test_request_context('/', headers={'X-MS-CLIENT-PRINCIPAL': header}):
            assert get_current_user_name() == 'jane@example.com'

    def test_falls_back_to_principal_name_header(self, app):
        with app.test_request_context('/', headers={'X-MS-CLIENT-PRINCIPAL-NAME': 'jane@example.com'}):
            assert get_current_user_name() == 'jane@example.com'

    def test_givenname_only(self, app):
        header = _make_principal(given='Jane')
        with app.test_request_context('/', headers={'X-MS-CLIENT-PRINCIPAL': header}):
            assert get_current_user_name() == 'Jane'


# ---------------------------------------------------------------------------
# role_required decorator
# ---------------------------------------------------------------------------

class TestRoleRequired:
    def test_no_auth_header_returns_401(self, client):
        # /version-history requires pam_users; no headers → 401
        # Disable dev-mode fallback so the request is truly unauthenticated
        with patch('auth._is_local_dev_mode', return_value=False):
            resp = client.get('/version-history')
        assert resp.status_code == 401

    def test_insufficient_role_returns_403(self, client):
        # pam_viewonly cannot access pam_users routes
        header = _make_principal(name='Viewer')
        claims = [{'typ': 'roles', 'val': 'ViewOnly'}]
        payload = json.dumps({'claims': claims})
        b64 = base64.b64encode(payload.encode()).decode()
        resp = client.get('/version-history', headers={
            'X-MS-CLIENT-PRINCIPAL': b64,
            'X-MS-CLIENT-PRINCIPAL-NAME': 'viewer@example.com',
        })
        assert resp.status_code == 403

    def test_sufficient_role_allows_access(self, client):
        claims = [{'typ': 'roles', 'val': 'User'}]
        payload = json.dumps({'claims': claims})
        b64 = base64.b64encode(payload.encode()).decode()
        resp = client.get('/version-history', headers={
            'X-MS-CLIENT-PRINCIPAL': b64,
            'X-MS-CLIENT-PRINCIPAL-NAME': 'user@example.com',
        })
        # 200 or redirect is fine; just not 401/403
        assert resp.status_code not in (401, 403)
