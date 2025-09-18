"""Tests for the admin dashboard summary endpoint and KPI rendering.

Relies on the shared Flask `client` fixture provided by `conftest.py`.
"""

def test_dashboard_summary_endpoint(client):
    resp = client.get('/admin/dashboard-summary')
    assert resp.status_code == 200
    data = resp.get_json()
    # Accept flattened response fields or nested under 'summary'
    source = data
    if 'summary' in data and isinstance(data['summary'], dict):
        # We expect flattened keys also present; but fallback for nested only
        source = data if 'total_promos' in data else data['summary']
    for key in ['total_promos','active_promos','unique_owners','pcr_events','pcr_promos','invalid_date_ratio']:
        assert key in source
    # Basic type sanity
    assert isinstance(source['total_promos'], int)
    assert isinstance(source['active_promos'], int)
    assert isinstance(source['unique_owners'], int)


def test_admin_page_contains_kpi_elements(client):
    resp = client.get('/admin')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    # Ensure KPI bar container & expected KPI ids
    for kpi_id in [
        'kpi-total-promos','kpi-active-promos','kpi-owners',
        'kpi-cache','kpi-pcr','kpi-date'
    ]:
        assert f'id="{kpi_id}"' in html
    # Basic structural checks
    assert 'class="kpi-bar"' in html
    # Ensure script loader present
    assert 'loadDashboardSummary' in html
    # Placeholder for tooltip attribute existence (static markup before JS sets values)
    # At least elements should be ready for data-tip injection
    assert 'id="kpi-total-promos"' in html
