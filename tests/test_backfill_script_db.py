import os
import runpy
import sys

import pytest
from dotenv import load_dotenv


load_dotenv()


def _require_pam_db() -> None:
    if not os.getenv('PAM_DB_SERVER'):
        pytest.skip('PAM_DB_SERVER not set')


def test_backfill_script_dry_run():
    _require_pam_db()
    sys.argv = ['scripts/backfill_zlab_event_types.py']
    runpy.run_path('scripts/backfill_zlab_event_types.py', run_name='__main__')
