"""Centralized Version History Service (SQLite-backed).

Reads the existing SQLite `version_history` table written by
`DatabaseManager.record_version_entry` (schema: id, promo_code, timestamp,
change_type, description, user_name, diff_json). Provides higher-level access
patterns for UI pages (summary + full history) without coupling the admin
blueprint directly to low-level SQL.

This intentionally DOES NOT re‑implement write logic; we leverage existing
calls in the codebase that already insert rows via DatabaseManager.
Future enhancements could migrate all writers to this service for consistency.
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
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS version_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        promo_code TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        change_type TEXT NOT NULL,
                        description TEXT NOT NULL,
                        user_name TEXT NULL,
                        diff_json TEXT NULL
                    )
                    """
                )
                # Backward compatible migrations
                try:
                    cur = conn.execute("PRAGMA table_info(version_history)")
                    cols = {r[1] for r in cur.fetchall()}
                    if 'user_name' not in cols:
                        conn.execute("ALTER TABLE version_history ADD COLUMN user_name TEXT NULL")
                    if 'diff_json' not in cols:
                        conn.execute("ALTER TABLE version_history ADD COLUMN diff_json TEXT NULL")
                except Exception:
                    pass
        except Exception:
            # Fail silently; reader methods will surface errors
            pass

    # ---- Read APIs ----
    def get_promo_history(self, promo_code: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cols = {r[1] for r in conn.execute("PRAGMA table_info(version_history)").fetchall()}
                has_diff = 'diff_json' in cols
                has_user = 'user_name' in cols
                cur = conn.execute(
                    """
                    SELECT promo_code, timestamp, change_type, description, user_name, diff_json, id
                    FROM version_history
                    WHERE promo_code=?
                    ORDER BY timestamp DESC, id DESC
                    """,
                    (promo_code,)
                )
                raw_rows = cur.fetchall()
                for r in raw_rows:
                    if has_diff:
                        diff_raw = r['diff_json']
                    else:
                        diff_raw = r['field_changes'] if 'field_changes' in r.keys() else None
                    try:
                        diff = json.loads(diff_raw) if diff_raw else None
                    except Exception:
                        diff = None
                    ctype = r['change_type']
                    if ctype == 'Edit':  # backward compatibility
                        ctype = 'Modified'
                    elif ctype == 'Create':
                        ctype = 'Created'
                    if has_user:
                        changed_by = r['user_name'] or 'Unknown'
                    else:
                        changed_by = r['changed_by'] if 'changed_by' in r.keys() else 'Unknown'
                    rows.append({
                        'change_type': ctype,
                        'timestamp': r['timestamp'],
                        'changed_by': changed_by,
                        'description': r['description'],
                        'field_changes': diff
                    })
                # Inject version numbers for PCR events missing version metadata
                self._inject_versions(rows)
                self._inject_version_history_field(rows)
                self._prune_blank_updates(rows)
        except Exception:
            pass
        return rows

    def get_all_promotions_with_history(self, fetch_promos: Callable[[], Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return list of promotion summaries + their change collections.

        fetch_promos: callable returning mapping code->promo dict (owner, dates, etc.).
        """
        try:
            all_promos = fetch_promos() or {}
        except Exception:
            all_promos = {}

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cols = {r[1] for r in conn.execute("PRAGMA table_info(version_history)").fetchall()}
                has_diff = 'diff_json' in cols
                has_user = 'user_name' in cols
                cur = conn.execute(
                    """
                    SELECT promo_code, timestamp, change_type, description, user_name, diff_json, id
                    FROM version_history
                    ORDER BY timestamp DESC, id DESC
                    """
                )
                grouped: Dict[str, List[Dict[str, Any]]] = {}
                raw_rows = cur.fetchall()
                for r in raw_rows:
                    code = r['promo_code']
                    if has_diff:
                        diff_raw = r['diff_json']
                    else:
                        diff_raw = r['field_changes'] if 'field_changes' in r.keys() else None
                    try:
                        diff = json.loads(diff_raw) if diff_raw else None
                    except Exception:
                        diff = None
                    ctype = r['change_type']
                    if ctype == 'Edit':
                        ctype = 'Modified'
                    elif ctype == 'Create':
                        ctype = 'Created'
                    changed_by = r['user_name'] if has_user else (r['changed_by'] if 'changed_by' in r.keys() else 'Unknown')
                    grouped.setdefault(code, []).append({
                        'change_type': ctype,
                        'timestamp': r['timestamp'],
                        'changed_by': changed_by or 'Unknown',
                        'description': r['description'],
                        'field_changes': diff
                    })
        except Exception:
            return []

        result: List[Dict[str, Any]] = []
        for code, changes in grouped.items():
            # Enrich versions for PCR events
            self._inject_versions(changes)
            self._inject_version_history_field(changes)
            self._collapse_same_timestamp(changes)
            self._prune_blank_updates(changes)
            base = all_promos.get(code, {})
            result.append({
                'promo_code': code,
                'orbit_id': base.get('orbit_id', ''),
                'status': base.get('Status', '') or base.get('status', ''),
                'bill_facing_name': base.get('bill_facing_name', ''),
                'start_date': base.get('promo_start_date', ''),
                'end_date': base.get('promo_end_date', ''),
                'promo_owner': base.get('owner', ''),
                'changes': changes
            })

        result.sort(key=lambda p: (p['changes'][0]['timestamp'] if p['changes'] else ''), reverse=True)
        return result

    # --- helpers ---
    def _inject_versions(self, changes: List[Dict[str, Any]]):
        """Assign sequential version numbers to PCR / Date Mismatch SQL events lacking one.
        Modifies list in-place.
        """
        # Work oldest->newest for deterministic numbering
        pcr_counter = 0
        dm_counter = 0
        for ch in sorted(changes, key=lambda c: c.get('timestamp','')):
            ctype = ch.get('change_type')
            if ctype == 'PCR Version':
                pcr_counter += 1
                fc = ch.get('field_changes') or {}
                if 'version' not in fc:
                    fc['version'] = pcr_counter
                    ch['field_changes'] = fc
                # Harmonize description if generic
                if ch.get('description','').startswith('PCR SQL generated'):
                    ch['description'] = f'PCR Version #{fc["version"]} generated'
            elif ctype == 'Date Mismatch SQL':
                dm_counter += 1
                fc = ch.get('field_changes') or {}
                if 'version' not in fc:
                    fc['version'] = dm_counter
                    ch['field_changes'] = fc
                if ch.get('description','').startswith('Date mismatch SQL generated'):
                    ch['description'] = f'Date Mismatch SQL #{fc["version"]} generated'

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
        """Collapse multiple Created/Modified entries sharing the exact same timestamp.

        PCR Version / Date Mismatch SQL events are left untouched (even if same timestamp)
        to preserve discrete version semantics.
        """
        if not changes:
            return
        precedence = {'Created': 0, 'Create': 0, 'Modified': 1, 'Edit': 1}
        grouped = {}
        ordered: List[Dict[str, Any]] = []
        for ch in changes:
            ts = ch.get('timestamp')
            ctype = ch.get('change_type')
            if ctype not in ('Created','Create','Modified','Edit') or not ts:
                # passthrough (no collapse key)
                ordered.append(ch)
                continue
            key = ts  # collapse by second-level timestamp
            existing = grouped.get(key)
            if not existing:
                grouped[key] = ch
                ordered.append(ch)
            else:
                # Merge into existing representative
                rep = existing
                # Prefer higher precedence (Created beats Modified)
                if precedence.get(ctype, 99) < precedence.get(rep.get('change_type'), 99):
                    rep['change_type'] = 'Created' if ctype in ('Created','Create') else 'Modified'
                    rep['description'] = ch.get('description') or rep.get('description')
                # Merge field diffs
                rep_fc = rep.get('field_changes') or {}
                ch_fc = ch.get('field_changes') or {}
                # Merge version_history new list
                if 'version_history' in rep_fc and 'version_history' in ch_fc:
                    try:
                        rep_list = rep_fc['version_history'].get('new') or []
                        add_list = ch_fc['version_history'].get('new') or []
                        rep_fc['version_history']['new'] = list(dict.fromkeys(rep_list + add_list))
                    except Exception:
                        pass
                elif 'version_history' in ch_fc and 'version_history' not in rep_fc:
                    rep_fc['version_history'] = ch_fc['version_history']
                for f, diff in ch_fc.items():
                    if f == 'version_history':
                        continue
                    if f not in rep_fc:
                        rep_fc[f] = diff
                rep['field_changes'] = rep_fc
        # Replace list with collapsed ordering
        changes.clear()
        changes.extend(ordered)

    def _prune_blank_updates(self, changes: List[Dict[str, Any]]):
        """Remove Modified events that have no meaningful field-level diffs.

        A 'blank' update is one where field_changes is empty or only contains
        non-user facing internal keys (version_history + ignored set).
        """
        if not changes:
            return
        ignored = {
            'version_history','updated_at','created_at','last_sync','generated_sql',
            'full_sql','sql_text','pcr_sql','sql_preview','sql_payload','spe_generated_sql'
        }
        pruned: List[Dict[str, Any]] = []
        for ch in changes:
            ctype = ch.get('change_type')
            if ctype not in ('Modified','Edit'):
                pruned.append(ch)
                continue
            fc = ch.get('field_changes') or {}
            # Determine if any renderable diff remains
            has_renderable = False
            for f, diff in fc.items():
                if f in ignored:
                    continue
                if isinstance(diff, dict):
                    has_renderable = True
                    break
            if has_renderable:
                pruned.append(ch)
        changes.clear()
        changes.extend(pruned)


# Singleton instance for simple import usage
version_history_service = VersionHistoryService()

__all__ = [
    'VersionHistoryService',
    'version_history_service'
]
