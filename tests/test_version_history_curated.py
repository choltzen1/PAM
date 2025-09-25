import os
import sys
import tempfile
import shutil

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data.version_history import VersionHistoryManager

def test_curated_history_filters_modified_and_includes_versions():
    tmp = tempfile.mkdtemp()
    try:
        vh = VersionHistoryManager(data_dir=tmp)
        promo = 'PTEST'
        vh.record_promo_creation(promo, 'alice', {'code': promo, 'owner':'alice'})
        vh.record_promo_modification(promo, 'alice', {'updated_at': {'old':'x','new':'y'}})
        vh.record_promo_modification(promo, 'alice', {'status': {'old':'Draft','new':'Active'}, 'generated_sql': {'old':'A','new':'B'}})
        vh.record_sql_generation(promo, 'alice', 0.5, 1200)
        vh.record_sql_generation(promo, 'alice', 0.6, 1300)
        vh.record_date_mismatch_sql(promo, 'alice', 0.7, 1400)
        vh.record_file_upload(promo, 'alice', 'spreadsheet', 'file.xlsx')

        curated = vh.get_curated_promo_changes(promo)
        ctypes = [c['change_type'] for c in curated]
        assert 'Created' in ctypes
        assert ctypes.count('PCR Version') == 2
        assert 'Date Mismatch SQL' in ctypes
        assert 'File Upload' in ctypes
        assert ctypes.count('Modified') == 1
        modified_entries = [c for c in curated if c['change_type']=='Modified']
        assert 'generated_sql' not in modified_entries[0]['field_changes']
        assert 'status' in modified_entries[0]['field_changes']
        pcr_entries = [c for c in curated if c['change_type'] == 'PCR Version']
        assert any('version' in (e.get('field_changes') or {}) for e in pcr_entries)
        # Ensure PCR metadata includes generation timestamp and time
        assert any('sql_generated_at' in (e.get('field_changes') or {}) for e in pcr_entries)
        assert any('sql_generation_time' in (e.get('field_changes') or {}) for e in pcr_entries)
    finally:
        # Best-effort cleanup
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass
