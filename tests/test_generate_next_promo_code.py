import pytest

def test_generate_next_simple_increment(client, monkeypatch):
    from data import database as dbmod
    monkeypatch.setattr(dbmod.DatabaseManager, 'get_highest_sequential_promo_code', lambda self: 'R333')
    r = client.get('/api/generate_next_promo_code')
    assert r.status_code == 200
    js = r.get_json()
    assert js['next_code'] == 'R334'
    assert js['rolled'] is False

def test_generate_next_letter_rollover(client, monkeypatch):
    from data import database as dbmod
    monkeypatch.setattr(dbmod.DatabaseManager, 'get_highest_sequential_promo_code', lambda self: 'R9999')
    # R9999 + 1 -> rollover to S001 (since we allow up to 4 digits now; hitting >9999 triggers rollover)
    r = client.get('/api/generate_next_promo_code')
    assert r.status_code == 200
    js = r.get_json()
    assert js['next_code'].startswith('S')
    assert js['rolled'] is True