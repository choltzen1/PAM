import pytest

pytestmark = pytest.mark.no_external_writes

@pytest.mark.usefixtures('client')
def test_generate_next_with_orbit_monkeypatched(client, monkeypatch):
    from services.promo_code_workflow import PromoCodeWorkflow
    monkeypatch.setattr(
        PromoCodeWorkflow,
        'create_from_orbit',
        lambda self, orbit_id, execution_type='RDC', user='System', config='': {
            'success': True,
            'code': 'R902',
            'orbit_id': orbit_id,
            'rolled': False,
        }
    )
    r = client.get('/api/generate_next_promo_code?orbit_id=26684')
    assert r.status_code == 200
    js = r.get_json()
    assert js.get('success') is True
    assert js.get('promo_code') == 'R902'
    assert js.get('orbit_id') == '26684'
