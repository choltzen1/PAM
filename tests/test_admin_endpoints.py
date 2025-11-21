import pytest

# Uses shared fixtures from conftest.py

def test_admin_dashboard_page(client):
    resp = client.get('/admin')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Promotions Count'.lower().split()[0] in body.lower() or 'Admin'.lower() in body.lower()

def test_admin_stats_endpoint(client):
    resp = client.get('/admin/stats')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert data.get('success') is True
    assert 'stats' in data

# Version history page removed; corresponding UI test deleted
