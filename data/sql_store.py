import os, sqlite3, hashlib
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

DB_PATH = os.path.join('data', 'version_history.db')  # reuse existing file, separate table

DDL = """
CREATE TABLE IF NOT EXISTS generated_sql_store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    promo_code TEXT NOT NULL,
    stored_at TEXT NOT NULL,
    sql_length INTEGER NOT NULL,
    sql_hash TEXT NOT NULL,
    generation_time REAL,
    source TEXT,
    sql_text TEXT
);
CREATE INDEX IF NOT EXISTS idx_generated_sql_promo ON generated_sql_store(promo_code, stored_at);
"""

def _ensure():
    os.makedirs('data', exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        for stmt in DDL.strip().split(';'):
            s = stmt.strip()
            if s:
                conn.execute(s)

_ensure()

def save_generated_sql(promo_code: str, sql_text: str, generation_time: float, source: str = 'generator') -> str:
    """Persist full generated SQL; returns md5 hash."""
    h = hashlib.md5(sql_text.encode('utf-8')).hexdigest()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO generated_sql_store (promo_code, stored_at, sql_length, sql_hash, generation_time, source, sql_text) VALUES (?,?,?,?,?,?,?)",
            (promo_code, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), len(sql_text), h, generation_time, source, sql_text)
        )
    return h

def get_latest_generated_sql(promo_code: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM generated_sql_store WHERE promo_code=? ORDER BY id DESC LIMIT 1",
            (promo_code,)
        ).fetchone()
        if not row:
            return None, None
        meta = {k: row[k] for k in ('stored_at','sql_length','sql_hash','generation_time','source','id')}
        return row['sql_text'], meta
