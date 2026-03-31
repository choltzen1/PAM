import pytest

pytestmark = pytest.mark.no_external_writes

def test_generate_next_simple_increment(client, monkeypatch):
    from services.promo_code_workflow import PromoCodeWorkflow
    monkeypatch.setattr(
        PromoCodeWorkflow,
        'create_from_orbit',
        lambda self, orbit_id, execution_type='RDC', user='System', config='', broken_trade='N': {
            'success': True,
            'code': 'R901',
            'orbit_id': orbit_id,
            'rolled': False,
        }
    )
    r = client.get('/api/generate_next_promo_code?orbit_id=26684')
    assert r.status_code == 200
    js = r.get_json()
    assert js.get('success') is True
    assert js.get('promo_code') == 'R901'


def test_generate_next_letter_rollover(client, monkeypatch):
    from services.promo_code_workflow import PromoCodeWorkflow
    monkeypatch.setattr(
        PromoCodeWorkflow,
        'create_from_orbit',
        lambda self, orbit_id, execution_type='RDC', user='System', config='', broken_trade='N': {
            'success': True,
            'code': 'S001',
            'orbit_id': orbit_id,
            'rolled': True,
        }
    )
    r = client.get('/api/generate_next_promo_code?orbit_id=26684')
    assert r.status_code == 200
    js = r.get_json()
    assert js.get('success') is True
    assert js.get('promo_code', '').startswith('S')
    assert js['rolled'] is True