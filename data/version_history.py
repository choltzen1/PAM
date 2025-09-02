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
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.db_path = os.path.join(data_dir, "version_history.db")
        self._init_database()
    
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
                ORDER BY timestamp DESC
            """, (promo_code,))
            
            changes = []
            for row in cursor.fetchall():
                change = dict(row)
                if change['field_changes']:
                    change['field_changes'] = json.loads(change['field_changes'])
                changes.append(change)
            
            return changes
    
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
        field_descriptions = []
        for field, changes in changed_fields.items():
            old_val = changes.get('old', 'None')
            new_val = changes.get('new', 'None')
            field_descriptions.append(f"{field}: '{old_val}' → '{new_val}'")
        
        description = f"Updated {', '.join(changed_fields.keys())}: {'; '.join(field_descriptions)}"
        
        self.record_change(
            promo_code=promo_code,
            change_type="Modified",
            changed_by=changed_by,
            description=description,
            field_changes=changed_fields
        )
    
    def record_sql_generation(self, promo_code: str, changed_by: str, generation_time: float, sql_length: int):
        """Record SQL generation for a promotion"""
        description = "Generated SQL (PROMO_ELIGIBILITY_RULES)"
        
        self.record_change(
            promo_code=promo_code,
            change_type="SQL Generated",
            changed_by=changed_by,
            description=description,
            field_changes={
                "generation_time": generation_time,
                "sql_length": sql_length,
                "generated_at": datetime.now().isoformat()
            }
        )
    
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
