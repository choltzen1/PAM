import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sqlalchemy import text

from data.database import DatabaseManager

DEFAULT_QUERY = (
    "SELECT * FROM OPENQUERY(PEFPEP_RO, '"
    "SELECT TABLE_OWNER AS LIVE_REFERENCE, "
    "CASE "
    "WHEN TABLE_OWNER = ''EFPEBATCHPROD01REFB'' THEN ''EFPEBATCHPROD01REFA'' "
    "ELSE ''EFPEBATCHPROD01REFB'' "
    "END AS STAGING_REFERENCE "
    "FROM ALL_SYNONYMS "
    "WHERE TABLE_NAME = UPPER(''promo_eligibility_rules'') "
    "AND OWNER = ''EFPEBATCHPROD01C''"
    "');"
)

DEFAULT_PATH = os.path.join('data', 'staging_schema_reference.json')


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_reference(path: Optional[str] = None) -> Dict[str, Any]:
    ref_path = path or os.getenv('STAGING_SCHEMA_REF_PATH', DEFAULT_PATH)
    if not os.path.exists(ref_path):
        return {}
    try:
        with open(ref_path, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_reference(data: Dict[str, Any], path: Optional[str] = None) -> None:
    ref_path = path or os.getenv('STAGING_SCHEMA_REF_PATH', DEFAULT_PATH)
    os.makedirs(os.path.dirname(ref_path), exist_ok=True)
    payload = dict(data)
    payload['updated_at'] = _now_iso()
    with open(ref_path, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, indent=2)


def fetch_staging_reference(
    db_manager: Optional[DatabaseManager] = None,
    query: Optional[str] = None
) -> Dict[str, Any]:
    dm = db_manager or DatabaseManager()
    sql = query or os.getenv('STAGING_SCHEMA_QUERY', DEFAULT_QUERY)

    engine = dm.get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(sql)).fetchone()
        if not row:
            raise RuntimeError('No staging reference returned from OPENQUERY')
        mapping = row._mapping
        return {
            'live_reference': mapping.get('LIVE_REFERENCE') or mapping.get('live_reference'),
            'staging_reference': mapping.get('STAGING_REFERENCE') or mapping.get('staging_reference')
        }


def refresh_staging_reference(
    db_manager: Optional[DatabaseManager] = None,
    query: Optional[str] = None,
    path: Optional[str] = None
) -> Dict[str, Any]:
    data = fetch_staging_reference(db_manager=db_manager, query=query)
    save_reference(data, path=path)
    return data
