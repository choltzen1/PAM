import tempfile, json, os, sys
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path: sys.path.insert(0, ROOT)
from data.version_history import VersionHistoryManager

def test_duplicate_modified_suppressed_and_null_display():
    tmp = tempfile.mkdtemp()
    vh = VersionHistoryManager(data_dir=tmp)
    promo = 'PDUP'
    # First modification (old missing -> NULL)
    vh.record_promo_modification(promo, 'tester', {
        'trade_tier_1_amount': {'old': None, 'new': 250}
    })
    # Duplicate (should be suppressed)
    vh.record_promo_modification(promo, 'tester', {
        'trade_tier_1_amount': {'old': None, 'new': 250}
    })
    history = vh.get_promo_history(promo)
    assert len(history) == 1
    entry = history[0]
    assert entry['change_type'] == 'Modified'
    assert 'trade_tier_1_amount' in entry['field_changes']
    # Ensure stored structure kept old/new None/250
    assert entry['field_changes']['trade_tier_1_amount']['old'] is None
    assert entry['field_changes']['trade_tier_1_amount']['new'] == 250
