"""Tests that verify HTTP security headers are present on all responses.

These tests exercise the @app.after_request hook added in factory.py and confirm
that the CSP, X-Frame-Options, X-Content-Type-Options, and Referrer-Policy headers
are set on both HTML and JSON responses.
"""
import os
import sys
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("PAM_VALIDATION_MODE", "1")

import factory as factory_module


@pytest.fixture(scope="module")
def sec_client():
    """Minimal test client that just needs the security headers wired up."""
    app = factory_module.create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def get_headers(client, path="/"):
    """GET a path and return the response headers dict."""
    resp = client.get(path)
    return resp.headers


# ---------------------------------------------------------------------------
# Security header assertions
# ---------------------------------------------------------------------------

class TestSecurityHeaders:
    def test_x_content_type_options(self, sec_client):
        headers = get_headers(sec_client)
        assert headers.get("X-Content-Type-Options") == "nosniff", (
            "X-Content-Type-Options must be 'nosniff'"
        )

    def test_x_frame_options(self, sec_client):
        headers = get_headers(sec_client)
        assert headers.get("X-Frame-Options") == "SAMEORIGIN", (
            "X-Frame-Options must be 'SAMEORIGIN'"
        )

    def test_referrer_policy(self, sec_client):
        headers = get_headers(sec_client)
        assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin", (
            "Referrer-Policy must be 'strict-origin-when-cross-origin'"
        )

    def test_content_security_policy_present(self, sec_client):
        headers = get_headers(sec_client)
        csp = headers.get("Content-Security-Policy", "")
        assert csp, "Content-Security-Policy header must be present"

    def test_csp_default_src_self(self, sec_client):
        csp = get_headers(sec_client).get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp

    def test_csp_allows_cdnjs(self, sec_client):
        """FontAwesome is served from cdnjs.cloudflare.com."""
        csp = get_headers(sec_client).get("Content-Security-Policy", "")
        assert "cdnjs.cloudflare.com" in csp

    def test_csp_allows_jsdelivr(self, sec_client):
        """Bootstrap Icons and Chart.js are served from cdn.jsdelivr.net."""
        csp = get_headers(sec_client).get("Content-Security-Policy", "")
        assert "cdn.jsdelivr.net" in csp

    def test_headers_present_on_api_route(self, sec_client):
        """Security headers should appear on JSON API responses too."""
        resp = sec_client.get("/api/get_promo_details/FAKE_CODE")
        # Route may 401/403/404 — we only care about headers, not status
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
