import os

import pytest
from dotenv import load_dotenv

from data.schema_reference import fetch_staging_reference, save_reference, load_reference


load_dotenv()


def _require_pam_db() -> None:
    if not os.getenv('PAM_DB_SERVER'):
        pytest.skip('PAM_DB_SERVER not set')


def test_fetch_staging_reference_returns_values():
    _require_pam_db()
    data = fetch_staging_reference()
    assert data.get('live_reference')
    assert data.get('staging_reference')


def test_save_and_load_reference_roundtrip(tmp_path):
    path = tmp_path / 'staging_ref.json'
    payload = {'live_reference': 'EFPEBATCHPROD01REFA', 'staging_reference': 'EFPEBATCHPROD01REFB'}
    save_reference(payload, path=str(path))
    loaded = load_reference(path=str(path))
    assert loaded['live_reference'] == payload['live_reference']
    assert loaded['staging_reference'] == payload['staging_reference']
    assert loaded.get('updated_at')
