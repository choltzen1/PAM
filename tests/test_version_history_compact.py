import os
import sys
from pathlib import Path

# Ensure project root on path when running this test in isolation
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.version_history import VersionHistoryManager


def test_compact_sql_generation_entry(tmp_path, monkeypatch):
    # Use temp directory for db
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    vh = VersionHistoryManager(data_dir=str(data_dir))

    vh.record_sql_generation('PROMO123', 'tester', generation_time=0.123, sql_length=456)

    history = vh.get_promo_history('PROMO123')
    assert len(history) == 1
    entry = history[0]
    assert entry['change_type'] == 'PCR Version'
    assert 'PCR Version #1' in entry['description']
    assert entry['field_changes'] is not None
    assert entry['field_changes']['context'] == 'pcr'
    assert 'sql_generation_time' in entry['field_changes']


def test_only_changed_fields_recorded(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    vh = VersionHistoryManager(data_dir=str(data_dir))

    # Simulate creation then modification with limited fields
    vh.record_promo_creation('PROMO999', 'creator', {'field_a': 'A', 'field_b': 'B', 'field_c': 'C'})
    vh.record_promo_modification('PROMO999', 'editor', {
        'field_b': {'old': 'B', 'new': 'B2'},
        'field_c': {'old': 'C', 'new': 'C2'}
    })

    history = vh.get_promo_history('PROMO999')
    # Find modification entry
    mod_entry = next(e for e in history if e['change_type'] == 'Modified')
    assert 'field_a' not in mod_entry.get('field_changes', {})
    assert 'field_b' in mod_entry['field_changes']
    assert 'field_c' in mod_entry['field_changes']
    # Ensure description is compact (no old/new arrow pairs)
    assert '→' not in mod_entry['description']


def test_excluded_generated_sql_field(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    vh = VersionHistoryManager(data_dir=str(data_dir))

    vh.record_promo_modification('PROMO777', 'user', {
        'generated_sql': {'old': '', 'new': 'HUGE SQL BLOB ...'},
        'promo_end_date': {'old': '2025-01-01', 'new': '2025-02-01'}
    })

    history = vh.get_promo_history('PROMO777')
    assert len(history) == 1
    entry = history[0]
    assert 'generated_sql' not in entry['field_changes']
    assert 'promo_end_date' in entry['field_changes']


def test_pcr_version_increment(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    vh = VersionHistoryManager(data_dir=str(data_dir))

    vh.record_sql_generation('PROMOABC', 'user', 0.05, 1000)
    vh.record_sql_generation('PROMOABC', 'user', 0.07, 1200)
    history = vh.get_promo_history('PROMOABC')
    versions = [h for h in history if h['change_type'] == 'PCR Version']
    assert len(versions) == 2
    assert any('PCR Version #1' in v['description'] for v in versions)
    assert any('PCR Version #2' in v['description'] for v in versions)


def test_metric_only_modification_ignored(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    vh = VersionHistoryManager(data_dir=str(data_dir))
    # Only excluded fields
    vh.record_promo_modification('PROMO_METRIC', 'user', {
        'sql_length': {'old': None, 'new': 12345},
        'sql_generation_time': {'old': None, 'new': 0.12},
        'sql_generated_at': {'old': None, 'new': '2025-09-18 00:00:00'}
    })
    history = vh.get_promo_history('PROMO_METRIC')
    assert history == []


def test_timestamp_only_modification_ignored(tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    vh = VersionHistoryManager(data_dir=str(data_dir))
    # Simulate modification call directly
    vh.record_promo_modification('PROMO_TIME', 'user', {
        'updated_at': {'old': '2025-01-01T00:00:00', 'new': '2025-01-01T00:00:05'}
    })
    assert vh.get_promo_history('PROMO_TIME') == []
