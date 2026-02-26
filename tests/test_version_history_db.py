import os
import uuid

import pytest
from dotenv import load_dotenv
from sqlalchemy import text

from data.database import DatabaseManager
from data.version_history import get_next_zlab_gen_count, log_version_event


load_dotenv()


def _require_pam_db() -> None:
    if not os.getenv('PAM_DB_SERVER'):
        pytest.skip('PAM_DB_SERVER not set')


def _cleanup(conn, promo_code: str) -> None:
    conn.execute(
        text("DELETE FROM PAM.Version_History WHERE promo_code = :promo_code"),
        {'promo_code': promo_code}
    )


def test_log_version_event_inserts_row():
    _require_pam_db()
    dm = DatabaseManager()
    engine = dm.get_engine()
    promo_code = f"UT_ZLAB_{uuid.uuid4().hex[:8]}"

    with engine.begin() as conn:
        _cleanup(conn, promo_code)
        ok = log_version_event(
            promo_code=promo_code,
            promo_id=promo_code,
            event_type='zlab_inserted',
            actor='pytest',
            source='unit_test'
        )
        assert ok is True

        row = conn.execute(
            text(
                "SELECT event_type, actor, source FROM PAM.Version_History "
                "WHERE promo_code = :promo_code"
            ),
            {'promo_code': promo_code}
        ).fetchone()
        assert row is not None
        assert (row[0] or '').lower() == 'zlab_inserted'
        assert row[1] == 'pytest'
        assert row[2] == 'unit_test'

        _cleanup(conn, promo_code)


def test_get_next_zlab_gen_count_increments():
    _require_pam_db()
    dm = DatabaseManager()
    engine = dm.get_engine()
    promo_code = f"UT_ZLAB_{uuid.uuid4().hex[:8]}"

    with engine.begin() as conn:
        _cleanup(conn, promo_code)
        log_version_event(
            promo_code=promo_code,
            promo_id=promo_code,
            event_type='zlab_inserted',
            actor='pytest',
            source='unit_test'
        )
        log_version_event(
            promo_code=promo_code,
            promo_id=promo_code,
            event_type='zlab_insert_failed',
            actor='pytest',
            source='unit_test'
        )

        next_count = get_next_zlab_gen_count(promo_code)
        assert next_count == 3

        _cleanup(conn, promo_code)
