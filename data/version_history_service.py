"""New minimal Promotion History service (creation events only).

Legacy `version_history` table logic removed. We now rely exclusively on
`promo_history` rows produced by DatabaseManager.record_creation_event.
Each row: (promo_code, timestamp, event_type='Created', user_name, diff_json).

This reader supplies data in the same structure expected by the existing
version_history.html template: list of promotions each with 'changes' where
each change has: change_type, timestamp, changed_by, description, field_changes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Callable, Optional
import os, json, sqlite3

DB_PATH = os.path.join('data', 'version_history.db')


class VersionHistoryService:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self):  # idempotent
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # Only ensure promo_history exists (defensive – DatabaseManager also ensures)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS promo_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        promo_code TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        user_name TEXT,
                        diff_json TEXT
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_ph_code_ts ON promo_history(promo_code, timestamp)")
        except Exception:
            pass

    # ---- Read APIs ----
    def get_promo_history(self, promo_code: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    "SELECT promo_code, timestamp, event_type, user_name, diff_json FROM promo_history WHERE promo_code=? ORDER BY timestamp DESC, id DESC",
                    (promo_code,)
                )
                for r in cur.fetchall():
                    diff = None
                    try:
                        diff = json.loads(r['diff_json']) if r['diff_json'] else None
                    except Exception:
                        diff = None
                    evt = r['event_type']
                    if evt == 'Created':
                        desc = 'Created Promo'
                    elif evt == 'Updated':
                        desc = 'Updated Promo'
                    elif evt == 'SKU List Uploaded':
                        desc = 'SKU List Uploaded'
                    elif evt == 'Trade-In List Uploaded':
                        desc = 'Trade-In List Uploaded'
                    elif evt.startswith('PCR Version #'):
                        desc = evt
                    elif evt.startswith('System Updates End Date -'):
                         desc = evt
                    else:
                        desc = evt
                    rows.append({
                        'change_type': 'Created' if evt == 'Created' else evt,
                        'timestamp': r['timestamp'],
                        'changed_by': r['user_name'] or 'Unknown',
                        'description': desc,
                        'field_changes': diff
                    })
            # Provide synthetic version_history field for template uniformity
            self._inject_version_history_field(rows)
        except Exception:
            return []
        return rows

    def get_all_promotions_with_history(self, fetch_promos: Callable[[], Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return list of promotion summaries + their change collections.

        fetch_promos: callable returning mapping code->promo dict (owner, dates, etc.).
        """
        try:
            all_promos = fetch_promos() or {}
        except Exception:
            all_promos = {}
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute("SELECT promo_code, timestamp, event_type, user_name, diff_json FROM promo_history ORDER BY timestamp DESC, id DESC")
                for r in cur.fetchall():
                    diff = None
                    try:
                        diff = json.loads(r['diff_json']) if r['diff_json'] else None
                    except Exception:
                        diff = None
                    evt = r['event_type']
                    if evt == 'Created':
                        desc = 'Created Promo'
                    elif evt == 'Updated':
                        desc = 'Updated Promo'
                    elif evt == 'SKU List Uploaded':
                        desc = 'SKU List Uploaded'
                    elif evt == 'Trade-In List Uploaded':
                        desc = 'Trade-In List Uploaded'
                    elif evt.startswith('PCR Version #'):
                        desc = evt
                    elif evt.startswith('System Updates End Date -'):
                        desc = evt
                    else:
                        desc = evt
                    grouped.setdefault(r['promo_code'], []).append({
                        'change_type': 'Created' if evt == 'Created' else evt,
                        'timestamp': r['timestamp'],
                        'changed_by': r['user_name'] or 'Unknown',
                        'description': desc,
                        'field_changes': diff
                    })
        except Exception:
            pass
        result: List[Dict[str, Any]] = []
        for code, changes in grouped.items():
            self._inject_version_history_field(changes)
            base = all_promos.get(code, {})
            # Owner fallback: prefer sanitized base owner; if absent attempt to pull from earliest change diff
            owner_val = base.get('owner') or base.get('Owner')
            if not owner_val:
                for ch in changes:
                    fc = ch.get('field_changes') or {}
                    # Diff may store either canonical 'owner' or physical 'Owner'
                    diff_owner = fc.get('owner') or fc.get('Owner')
                    if isinstance(diff_owner, dict):
                        owner_val = diff_owner.get('new')
                    elif diff_owner:
                        owner_val = diff_owner
                    if owner_val:
                        break
            if isinstance(owner_val, str):
                strip_chars = '"\'""`'
                owner_val = owner_val.translate(str.maketrans('', '', strip_chars)).strip()
            else:
                owner_val = ''
            result.append({
                'promo_code': code,
                'orbit_id': base.get('orbit_id', ''),
                'status': base.get('Status', '') or base.get('status', ''),
                'bill_facing_name': base.get('bill_facing_name', ''),
                'start_date': base.get('promo_start_date', ''),
                'end_date': base.get('promo_end_date', ''),
                'promo_owner': owner_val,
                'changes': changes
            })
        result.sort(key=lambda p: (p['changes'][0]['timestamp'] if p['changes'] else ''), reverse=True)
        return result

    # --- helpers ---
    # Legacy helpers removed (no PCR/Date Mismatch events in new minimal history)

    def _inject_version_history_field(self, changes: List[Dict[str, Any]]):
        """Ensure every change has a synthetic version_history diff for UI consistency.

        If original diff lacked version_history, we create one with a single entry summarizing
        the event (timestamp - user - description). We do not overwrite existing.
        """
        for ch in changes:
            fc = ch.get('field_changes')
            if fc is None:
                fc = {}
                ch['field_changes'] = fc
            if 'version_history' not in fc:
                summary = f"{ch.get('timestamp','')} - {ch.get('changed_by','Unknown')} - {ch.get('description','')}".strip()
                fc['version_history'] = {'old': None, 'new': [summary]}

    def _collapse_same_timestamp(self, changes: List[Dict[str, Any]]):
        return  # no-op in minimal mode

    def _prune_blank_updates(self, changes: List[Dict[str, Any]]):
        return  # no-op (only creation events)

    def _consolidate_initial_creation(self, changes: List[Dict[str, Any]]):
        return  # no-op (only single creation events expected)


# Singleton instance for simple import usage
version_history_service = VersionHistoryService()

__all__ = [
    'VersionHistoryService',
    'version_history_service'
]
