import os
import pytest
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as c:
        yield c

def test_generate_sql_minimal_promo(client):
    promo_code = 'TESTE2E1'
    # First load page (GET)
    r1 = client.get(f'/edit_rdc/{promo_code}?tab=SQL%20Generation')
    assert r1.status_code == 200
    # Post generate sql
    r2 = client.post(f'/edit_rdc/{promo_code}', data={'active_tab':'SQL Generation','generate_sql':'1'})
    assert r2.status_code in (302, 303)
    # Follow redirect
    r3 = client.get(r2.headers['Location'])
    assert r3.status_code == 200
    # Expect diagnostic or real SQL text marker in response body
    body = r3.get_data(as_text=True)
    assert 'promo_eligibility_rules.sql' in body
    # Ensure at least placeholder SELECT present
    assert ('SELECT 1 AS no_data_placeholder' in body) or ('PROMO_ELIGIBILITY_RULES' in body)
    # Ensure file persisted
    expected_file = os.path.join('data','uploads','promotions', promo_code, f'{promo_code}_promo_eligibility_rules.sql')
    assert os.path.exists(expected_file), f'Missing generated SQL file: {expected_file}'
