"""Promo code tracking — thin DB-backed shim.

Previously tracked issued codes via data/issued_codes.json.
Now delegates to PAM.Promo_ID_Tracking (via DatabaseManager.get_all_allocated_ids).

The load_issued_codes / record_issued_code API is preserved for backward
compatibility with callers in api/routes.py, storage.py, and promo_code_workflow.py.
"""
from typing import Set


def load_issued_codes() -> Set[str]:
    """Return all ever-allocated promo codes from the tracking table."""
    try:
        from data.database import DatabaseManager
        dm = DatabaseManager()
        return dm.get_all_allocated_ids('code')
    except Exception:
        return set()


def record_issued_code(code: str):
    """No-op. Promo codes are recorded to the tracking table at creation time
    by promo_code_workflow.py via insert_tracking_record(). This function
    exists only for backward compatibility."""
    pass
