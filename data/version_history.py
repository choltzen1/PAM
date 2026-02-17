import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import text

from data.database import DatabaseManager


def _json_dump(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=True)
    except Exception:
        return None


def get_next_sql_gen_count(promo_code: str) -> int:
    """Return the next SQL generation count for a promo code."""
    dm = DatabaseManager()
    engine = dm.get_engine()
    sql = (
        "SELECT COUNT(1) AS cnt FROM PAM.Version_History "
        "WHERE promo_code = :promo_code AND event_type = 'pcr_generated'"
    )
    try:
        with engine.connect() as conn:
            row = conn.execute(text(sql), {'promo_code': promo_code}).fetchone()
            count = int(row[0]) if row and row[0] is not None else 0
            return count + 1
    except Exception:
        return 1


def log_version_event(
    *,
    promo_code: str,
    event_type: str,
    promo_id: Optional[str] = None,
    orbit_id: Optional[str] = None,
    promo_owner: Optional[str] = None,
    promo_type: Optional[str] = None,
    actor: Optional[str] = None,
    source: Optional[str] = None,
    version_number: Optional[int] = None,
    sql_gen_count: Optional[int] = None,
    approval_request_id: Optional[str] = None,
    approval_status: Optional[str] = None,
    approval_recipient: Optional[str] = None,
    approval_response_ts: Optional[str] = None,
    changed_fields: Optional[Dict[str, Any]] = None,
    created_snapshot: Optional[Dict[str, Any]] = None,
    event_ts: Optional[str] = None,
) -> bool:
    """Insert a version history event into PAM.Version_History."""
    dm = DatabaseManager()
    engine = dm.get_engine()

    event_ts_val = event_ts or datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    promo_id_val = promo_id or promo_code
    event_type_val = (event_type or '').lower()

    insert_sql = (
        "INSERT INTO PAM.Version_History ("
        "promo_id, promo_code, orbit_id, promo_owner, promo_type, "
        "event_type, event_ts, actor, source, "
        "version_number, sql_gen_count, approval_request_id, approval_status, "
        "approval_recipient, approval_response_ts, changed_fields, created_snapshot"
        ") VALUES ("
        ":promo_id, :promo_code, :orbit_id, :promo_owner, :promo_type, "
        ":event_type, :event_ts, :actor, :source, "
        ":version_number, :sql_gen_count, :approval_request_id, :approval_status, "
        ":approval_recipient, :approval_response_ts, :changed_fields, :created_snapshot"
        ")"
    )

    params = {
        'promo_id': promo_id_val,
        'promo_code': promo_code,
        'orbit_id': orbit_id,
        'promo_owner': promo_owner,
        'promo_type': promo_type,
        'event_type': event_type_val,
        'event_ts': event_ts_val,
        'actor': actor,
        'source': source,
        'version_number': version_number,
        'sql_gen_count': sql_gen_count,
        'approval_request_id': approval_request_id,
        'approval_status': approval_status,
        'approval_recipient': approval_recipient,
        'approval_response_ts': approval_response_ts,
        'changed_fields': _json_dump(changed_fields),
        'created_snapshot': _json_dump(created_snapshot),
    }

    try:
        with engine.begin() as conn:
            conn.execute(text(insert_sql), params)
        return True
    except Exception:
        return False
