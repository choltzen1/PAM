"""
Version History Tracking System for PAM
Tracks all changes to promotions with timestamps and user information
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

class VersionHistoryManager:
    """Manages version history tracking for promotions"""
    # Fields we never want to persist diffs for (too large / noisy)
    EXCLUDED_FIELDS = {
        'generated_sql', 'full_sql', 'sql_text', 'pcr_sql', 'spe_generated_sql',
        'sql_preview', 'sql_payload',
        # Trade-in and bulk insert style SQL bodies (never show)
        'tradein_sql_statements', 'trade_in_sql', 'sku_insert_sql', 'device_sql',
        # Internal flags only
        'sql_truncated'
    }
    PCR_METADATA_FIELDS = {'sql_generated_at', 'sql_generation_time', 'sql_length', 'version', 'context'}
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.db_path = os.path.join(data_dir, "version_history.db")
        self._init_database()
        # Startup sanitization removed now that curated retrieval filters noise.
    
    def _init_database(self):
        """Initialize the version history database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS version_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    promo_code TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    changed_by TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    description TEXT NOT NULL,
                    field_changes TEXT,  -- JSON string of field changes
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_promo_code ON version_history(promo_code)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON version_history(timestamp)
            """)
    
    def record_change(self, promo_code: str, change_type: str, changed_by: str, 
                     description: str, field_changes: Optional[Dict[str, Any]] = None):
        """Record a change to a promotion"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        field_changes_json = json.dumps(field_changes) if field_changes else None
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO version_history 
                (promo_code, change_type, changed_by, timestamp, description, field_changes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (promo_code, change_type, changed_by, timestamp, description, field_changes_json))
    
    def get_promo_history(self, promo_code: str) -> List[Dict[str, Any]]:
        """Get the complete change history for a promotion"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM version_history 
                WHERE promo_code = ? 
                ORDER BY timestamp DESC, id DESC
            """, (promo_code,))
            
            changes = []
            for row in cursor.fetchall():
                change = dict(row)
                if change['field_changes']:
                    change['field_changes'] = json.loads(change['field_changes'])
                changes.append(change)
            
            return changes

    def get_curated_promo_changes(self, promo_code: str) -> List[Dict[str, Any]]:
        """Return only the curated set of events for display.
        Includes: Created, Modified (with filtered diffs), PCR Version, Date Mismatch SQL, File Upload.
        Excludes: legacy 'SQL Generated', Modified entries whose field_changes collapse to empty after filtering.
        Field filtering: remove excluded SQL body fields and pure timestamp keys.
        """
        allowed_types = {"Created", "Modified", "PCR Version", "Date Mismatch SQL", "File Upload"}
        ts_keys = {"updated_at", "created_at", "last_sync"}
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM version_history
                WHERE promo_code=?
                ORDER BY timestamp DESC, id DESC
                """,
                (promo_code,)
            )
            curated: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                change = dict(row)
                ctype = change.get("change_type")
                if ctype not in allowed_types:
                    continue
                fc_raw = change.get("field_changes")
                if fc_raw:
                    try:
                        fc = json.loads(fc_raw)
                    except Exception:
                        fc = {}
                else:
                    fc = {}
                # Remove excluded and timestamp-only fields from diffs
                if ctype == "Modified" and fc:
                    filtered = {}
                    for field, details in fc.items():
                        if field in self.EXCLUDED_FIELDS or field in ts_keys:
                            continue
                        # Normalize possible key naming variations (old/new vs before/after)
                        if isinstance(details, dict):
                            old_val = details.get('old', details.get('before'))
                            new_val = details.get('new', details.get('after'))
                            # Skip if no semantic change (same value or both None)
                            if old_val == new_val:
                                continue
                            filtered[field] = {"old": old_val, "new": new_val}
                    if not filtered:
                        # Skip Modified entry that has no meaningful remaining diffs
                        continue
                    change['field_changes'] = filtered
                else:
                    if not fc:
                        change['field_changes'] = None
                    else:
                        if ctype in {"PCR Version", "Date Mismatch SQL"}:
                            meta_filtered = {k: v for k, v in fc.items() if k in self.PCR_METADATA_FIELDS}
                        else:
                            meta_filtered = {k: v for k, v in fc.items() if k not in self.EXCLUDED_FIELDS and k not in ts_keys}
                        change['field_changes'] = meta_filtered or None
                curated.append(change)
            return curated
    
    def get_all_promotions_with_history(self) -> List[Dict[str, Any]]:
        """Get all promotions that have version history with their basic info and change counts"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT 
                    promo_code,
                    COUNT(*) as total_changes,
                    MIN(timestamp) as first_change,
                    MAX(timestamp) as last_change
                FROM version_history 
                GROUP BY promo_code
                ORDER BY last_change DESC
            """)
            
            return [dict(row) for row in cursor.fetchall()]
    
    def record_promo_creation(self, promo_code: str, changed_by: str, promo_data: Dict[str, Any]):
        """Record the creation of a new promotion"""
        self.record_change(
            promo_code=promo_code,
            change_type="Created",
            changed_by=changed_by,
            description="Initial promotion creation",
            field_changes={"initial_data": promo_data}
        )
    
    def record_promo_modification(self, promo_code: str, changed_by: str, 
                                 changed_fields: Dict[str, Dict[str, Any]]):
        """Record modifications to a promotion"""
        # Filter out excluded / oversized fields
        cleaned = {k: v for k, v in changed_fields.items() if k not in self.EXCLUDED_FIELDS}
        # Remove pure timestamp-only noise
        NON_MEANINGFUL = {"updated_at", "created_at", "last_sync", "sql_generation_time", "sql_length", "sql_generated_at"}
        meaningful = {k: v for k, v in cleaned.items() if k not in NON_MEANINGFUL}
        if not meaningful:
            return

        # Duplicate suppression: if last Modified entry has identical field_changes, skip
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT field_changes FROM version_history WHERE promo_code=? AND change_type='Modified' ORDER BY timestamp DESC, id DESC LIMIT 1",
                    (promo_code,)
                ).fetchone()
                if row and row['field_changes']:
                    try:
                        last_fc = json.loads(row['field_changes'])
                    except Exception:
                        last_fc = {}
                    # Compare structure and values (old/new) exactly
                    if set(last_fc.keys()) == set(meaningful.keys()):
                        same = True
                        
                        for k, vals in meaningful.items():
                            prev = last_fc.get(k, {})
                            if not isinstance(prev, dict):
                                same = False
                                break
                            if prev.get('old') != vals.get('old') or prev.get('new') != vals.get('new'):
                                same = False
                                break
                        if same:
                            # Suppress duplicate
                            return
        except Exception:
            # Fail open (do not block modification recording if check errors)
            pass
        description = f"Updated fields: {', '.join(meaningful.keys())}"
        
        self.record_change(
            promo_code=promo_code,
            change_type="Modified",
            changed_by=changed_by,
            description=description,
            field_changes=meaningful
        )
    
    def _next_pcr_version(self, promo_code: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM version_history WHERE promo_code=? AND change_type='PCR Version'",
                (promo_code,)
            )
            count = cur.fetchone()[0]
            return count + 1

    def record_sql_generation(self, promo_code: str, changed_by: str, generation_time: float, sql_length: int):
        """Record (or increment) PCR version event (stores timing + length + generated timestamp)."""
        version_number = self._next_pcr_version(promo_code)
        print(f"[VersionHistory] Recording PCR Version #{version_number} for {promo_code} (len={sql_length}, time={generation_time})")
        self.record_change(
            promo_code=promo_code,
            change_type="PCR Version",
            changed_by=changed_by,
            description=f"PCR Version #{version_number}",
            field_changes={
                "context": "pcr",
                "version": version_number,
                "sql_generation_time": generation_time,
                "sql_length": sql_length,
                "sql_generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        )

    def record_date_mismatch_sql(self, promo_code: str, changed_by: str, generation_time: float, sql_length: int):
        """Record date mismatch SQL generation as separate version-like event (stores timing + length + timestamp)."""
        print(f"[VersionHistory] Recording Date Mismatch SQL for {promo_code} (len={sql_length}, time={generation_time})")
        self.record_change(
            promo_code=promo_code,
            change_type="Date Mismatch SQL",
            changed_by=changed_by,
            description="Date mismatch SQL generated",
            field_changes={
                "context": "date_mismatch",
                "sql_generation_time": generation_time,
                "sql_length": sql_length,
                "sql_generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        )

    def compact_sql_entries(self):
        """One-time (or callable) compaction: strip large SQL text from older rows.
        If a description begins with 'Generated SQL' but field_changes contains
        neither context nor metadata in new compact form, rewrite to compact version.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id, description, field_changes FROM version_history WHERE change_type='SQL Generated'").fetchall()
            for row in rows:
                desc = row['description']
                fc_raw = row['field_changes']
                needs_update = False
                if len(desc) > 2000:
                    # Convert legacy huge PCR or date mismatch entries to new compact forms
                    if 'DATE MISMATCH' in desc.upper():
                        desc = 'Date mismatch SQL generated'
                        conn.execute("UPDATE version_history SET change_type='Date Mismatch SQL' WHERE id=?", (row['id'],))
                    else:
                        # Map to PCR Version with inferred version count
                        # Determine current count excluding this row
                        cur = conn.execute("SELECT COUNT(*) FROM version_history WHERE promo_code=(SELECT promo_code FROM version_history WHERE id=?) AND change_type='PCR Version' AND id<>?", (row['id'], row['id']))
                        prior = cur.fetchone()[0]
                        inferred_version = prior + 1
                        desc = f'PCR Version #{inferred_version}'
                        conn.execute("UPDATE version_history SET change_type='PCR Version' WHERE id=?", (row['id'],))
                    needs_update = True
                # If field_changes missing context, add minimal metadata placeholder
                if fc_raw:
                    try:
                        fc = json.loads(fc_raw)
                    except Exception:
                        fc = {}
                else:
                    fc = {}
                if 'context' not in fc:
                    # Guess context based on description
                    if 'DATE MISMATCH' in desc.upper():
                        fc['context'] = 'date_mismatch'
                    else:
                        fc['context'] = 'pcr'
                    needs_update = True
                if needs_update:
                    conn.execute(
                        "UPDATE version_history SET description=?, field_changes=? WHERE id=?",
                        (desc, json.dumps(fc), row['id'])
                    )

    def sanitize_modified_entries(self):
        """Remove excluded fields (e.g., generated_sql) from existing Modified records and update descriptions."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id, description, field_changes FROM version_history WHERE change_type='Modified'").fetchall()
            for row in rows:
                fc_raw = row['field_changes']
                if not fc_raw:
                    continue
                try:
                    fc = json.loads(fc_raw)
                except Exception:
                    continue
                original_keys = set(fc.keys())
                modified = False
                for ex in list(original_keys):
                    if ex in self.EXCLUDED_FIELDS and ex in fc:
                        del fc[ex]
                        modified = True
                # Remove timestamp-only keys if they are the only remaining ones
                ts_keys = {"updated_at", "created_at", "last_sync"}
                remaining_non_ts = [k for k in fc.keys() if k not in self.EXCLUDED_FIELDS and k not in ts_keys]
                if not remaining_non_ts:
                    # Delete row if only timestamps / excluded remain
                    conn.execute("DELETE FROM version_history WHERE id=?", (row['id'],))
                    continue
                if not modified:
                    # Still ensure description doesn't advertise timestamp-only change
                    new_desc = f"Updated fields: {', '.join(remaining_non_ts)}"
                    conn.execute(
                        "UPDATE version_history SET description=?, field_changes=? WHERE id=?",
                        (new_desc, json.dumps({k: fc[k] for k in remaining_non_ts}), row['id'])
                    )
                    continue
                # Rebuild description based on remaining non-excluded, non-timestamp keys
                new_desc = f"Updated fields: {', '.join(remaining_non_ts)}"
                conn.execute(
                    "UPDATE version_history SET description=?, field_changes=? WHERE id=?",
                    (new_desc, json.dumps({k: fc[k] for k in remaining_non_ts}), row['id'])
                )

    def purge_timestamp_only_mods(self):
        """Delete Modified rows whose field_changes contain only timestamp/ignored fields.
        Run at startup to retroactively clean legacy data.
        """
        ts_keys = {"updated_at", "created_at", "last_sync"}
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id, field_changes FROM version_history WHERE change_type='Modified'").fetchall()
            for row in rows:
                fc_raw = row['field_changes']
                if not fc_raw:
                    continue
                try:
                    fc = json.loads(fc_raw)
                except Exception:
                    continue
                keys = set(fc.keys())
                if keys and keys.issubset(ts_keys):
                    conn.execute("DELETE FROM version_history WHERE id=?", (row['id'],))
    
    def record_file_upload(self, promo_code: str, changed_by: str, file_type: str, filename: str):
        """Record file upload for a promotion"""
        description = f"Uploaded {file_type}: {filename}"
        
        self.record_change(
            promo_code=promo_code,
            change_type="File Upload",
            changed_by=changed_by,
            description=description,
            field_changes={
                "file_type": file_type,
                "filename": filename,
                "uploaded_at": datetime.now().isoformat()
            }
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about version history"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Total changes
            total_changes = conn.execute("SELECT COUNT(*) as count FROM version_history").fetchone()['count']
            
            # Unique promotions
            unique_promos = conn.execute("SELECT COUNT(DISTINCT promo_code) as count FROM version_history").fetchone()['count']
            
            # Change types
            change_types = conn.execute("""
                SELECT change_type, COUNT(*) as count 
                FROM version_history 
                GROUP BY change_type
            """).fetchall()
            
            # Top contributors
            contributors = conn.execute("""
                SELECT changed_by, COUNT(*) as count 
                FROM version_history 
                GROUP BY changed_by 
                ORDER BY count DESC 
                LIMIT 5
            """).fetchall()
            
            return {
                "total_changes": total_changes,
                "unique_promotions": unique_promos,
                "change_types": [dict(row) for row in change_types],
                "top_contributors": [dict(row) for row in contributors]
            }
