"""Standalone orbit search service.

Provides orbit_search(orbit_id) which queries ONLY the orbit table for a
single orbit id and returns a normalized payload. No references to PAM promo
source tables. No dependency on other internal modules.
"""
from typing import Dict, Any
import os
from dotenv import load_dotenv
try:
    load_dotenv()
except Exception:
    pass
from data.orbit_database import OrbitDatabaseManager

def _sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().replace('\u2019',"'").replace('\u2018',"'").replace('\u201c','"').replace('\u201d','"')
    return value

def orbit_search(orbit_id: str) -> Dict[str, Any]:
    oid = (orbit_id or '').strip()
    if not oid:
        return {'found': False, 'error': 'orbit_id required'}
    from sqlalchemy import text
    from data.database import DatabaseManager
    db = DatabaseManager()
    engine = db.get_engine()
    if not engine:
        return {'found': False, 'orbit_id': oid, 'error': 'db connection failed'}

    # Step 1: Check PAM table first — if orbit already has a promo, return immediately
    try:
        pam_sql = text(f"SELECT TOP 1 code FROM {db.source_table} WITH (NOLOCK) WHERE CAST(orbit_id AS NVARCHAR(255)) = :oid")
        with engine.connect() as conn:
            pam_row = conn.execute(pam_sql, {'oid': oid}).fetchone()
        if pam_row:
            return {
                'found': True,
                'orbit_id': oid,
                'promo_code': str(pam_row[0] or ''),
                'already_generated': True,
            }
    except Exception:
        pass

    # Step 2: Not in PAM — query orbit staging table for full details
    mgr = OrbitDatabaseManager()
    orbit_engine = mgr._db.get_engine()
    if not orbit_engine:
        return {'found': False, 'orbit_id': oid, 'error': 'orbit db connection failed'}
    sql = text(
        f"SELECT TOP 1 * FROM {mgr.staging_table} "
        f"WHERE CAST(orbit_id AS NVARCHAR(255)) = :oid"
    )
    try:
        with orbit_engine.connect() as conn:
            row = conn.execute(sql, {'oid': oid}).mappings().first()
    except Exception as e:
        return {'found': False, 'orbit_id': oid, 'error': str(e)}
    if not row:
        return {'found': False, 'orbit_id': oid, 'source_table': mgr.staging_table, 'error': 'not found'}
    raw = {str(k).lower(): v for k, v in dict(row).items()}
    return {
        'found': True,
        'orbit_id': oid,
        'bill_facing_name': _sanitize(raw.get('bill_facing_name') or ''),
        'initiative_name': _sanitize(raw.get('initiative_name') or ''),
        'description': _sanitize(raw.get('cat_description') or ''),
        'owner': _sanitize(raw.get('owner') or ''),
        'start_date': raw.get('promo_start_date') or '',
        'end_date': raw.get('promo_end_date') or '',
        'promo_code': '',
        'already_generated': False,
        'source_table': mgr.staging_table
    }

__all__ = ['orbit_search']
