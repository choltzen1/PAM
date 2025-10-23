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
    mgr = OrbitDatabaseManager()
    data = mgr.get_orbit_record(oid)
    if not data or (isinstance(data, dict) and data.get('_error')):
        return {'found': False, 'orbit_id': oid, 'source_table': mgr.table, 'error': data.get('_error') if isinstance(data, dict) else 'lookup failed'}
    data = {k: _sanitize(v) for k,v in data.items()}
    return {
        'found': True,
        'orbit_id': oid,
        'bill_facing_name': data.get('bill_facing_name') or data.get('description',''),
        'description': data.get('description',''),
        'owner': data.get('Owner') or data.get('owner','') or '',
        'start_date': data.get('promo_start_date') or data.get('promo_srart_date',''),
        'end_date': data.get('promo_end_date',''),
        'source_table': mgr.table
    }

__all__ = ['orbit_search']
