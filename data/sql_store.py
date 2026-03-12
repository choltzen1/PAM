import os, hashlib
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any
from data.database import DatabaseManager

dm = DatabaseManager()

def save_generated_sql(promo_code: str, sql_text: str, generation_time: float, source: str = 'generator') -> str:
    """Persist full generated SQL into PAM.generated_sql_store; returns md5 hash."""
    h = hashlib.md5(sql_text.encode('utf-8')).hexdigest()
    insert_sql = (
        "INSERT INTO PAM.generated_sql_store (promo_code, generated_at, generation_time_seconds, sql_text, generated_by, sql_length, sql_hash, source)"
        " VALUES (:promo_code, :generated_at, :generation_time_seconds, :sql_text, :generated_by, :sql_length, :sql_hash, :source)"
    )
    params = {
        'promo_code': promo_code,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'generation_time_seconds': generation_time,
        'sql_text': sql_text,
        'generated_by': source,
        'sql_length': len(sql_text),
        'sql_hash': h,
        'source': source
    }
    try:
        engine = dm.get_engine()
        with engine.begin() as conn:
            conn.execute(insert_sql, params)
    except Exception:
        # best-effort: log upstream. We don't want to crash promo generation on telemetry failure
        pass
    return h

def get_latest_generated_sql(promo_code: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    select_sql = (
        "SELECT TOP 1 id, promo_code, generated_at, generation_time_seconds, sql_text, sql_hash, sql_length, generated_by, source"
        " FROM PAM.generated_sql_store WHERE promo_code = :code ORDER BY id DESC"
    )
    try:
        engine = dm.get_engine()
        with engine.connect() as conn:
            row = conn.execute(select_sql, {'code': promo_code}).fetchone()
            if not row:
                return None, None
            meta = {
                'stored_at': row['generated_at'],
                'sql_length': row['sql_length'],
                'sql_hash': row['sql_hash'],
                'generation_time': row['generation_time_seconds'],
                'source': row['source'],
                'id': row['id']
            }
            return row['sql_text'], meta
    except Exception:
        return None, None
