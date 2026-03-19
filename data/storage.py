import json
import logging
import os
from dotenv import load_dotenv
import shutil
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from .database import DatabaseManager
from .field_map import FIELD_DB_MAP, READ_ONLY_FIELDS, EDITABLE_CANONICAL_FIELDS
from .version_history import log_version_event

logger = logging.getLogger(__name__)


class PromoDataManager:
    """Manages persistent storage for promotion data using live database connection"""
    def __init__(self, data_dir: str = "data"):
        # Ensure environment variables are loaded before initializing DatabaseManager
        try:
            load_dotenv()
        except Exception:
            pass
        self.data_dir = data_dir
        self.uploads_dir = os.path.join(data_dir, "uploads")
        self.promo_uploads_dir = os.path.join(self.uploads_dir, "promotions")
        # JSON file path for SPE promotions (not yet migrated to DB)
        self.spe_file = os.path.join(data_dir, "spe_promotions.json")
        self._auto_archive_spe_json()
        # Initialize database manager for live data
        self.db_manager = DatabaseManager()
        # Ensure upload directories exist
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(self.uploads_dir, exist_ok=True)
        os.makedirs(self.promo_uploads_dir, exist_ok=True)
        # Phase sweep tracking (string date YYYY-MM-DD or None)
        self._last_phase_sweep_date = None  # type: ignore[attr-defined]

    # --- Minimal compatibility API (legacy hybrid manager expectations) ---
    def get_cache_status(self) -> Dict[str, Any]:
        """Return a synthetic 'cache status' structure for admin endpoints.

        Legacy admin routes expect a caching layer (hybrid_storage). In the DB-only
        manager there is no in-memory promo cache; fabricate a minimal object that
        satisfies tests/UI without implying stale data risk.
        """
        return {
            'cached_items': 0,
            'cache_age_seconds': 0,
            'cache_age_minutes': 0,
            'cache_valid': True,
            'cache_ttl_minutes': 0,
            'last_refresh': None,
            'last_db_check': datetime.now(timezone.utc).isoformat(),
            'total_cache_hits': 0,
            'total_cache_misses': 0,
            'total_db_loads': 0,
            'cache_hit_ratio': 'N/A',
            'background_refresh_active': False
        }

    def _auto_archive_spe_json(self) -> None:
        """One-time rename of spe_promotions.json → .bak when it exists alongside DB records."""
        bak_path = self.spe_file + '.bak'
        try:
            if os.path.exists(self.spe_file) and not os.path.exists(bak_path):
                os.rename(self.spe_file, bak_path)
            if os.path.exists(bak_path):
                self.spe_file = bak_path
        except Exception:
            pass
    
    def _load_json(self, filepath: str) -> Dict[str, Any]:
        """Load data from JSON file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_json(self, filepath: str, data: Dict[str, Any]):
        """Save data to JSON file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_promo(self, promo_code: str) -> Dict[str, Any]:
        """Get a specific promotion by code (DB only).

        Legacy JSON override removed: always reflect current DB state.
        """
        try:
            db_record = self.db_manager.get_promo_by_code(promo_code)
            if db_record:
                converted = self.db_manager.convert_db_record_to_json_format(db_record)
                # Compute current phase and log transition (detail view)
                try:
                    phase = self._compute_phase(converted.get('promo_start_date'), converted.get('promo_end_date'))
                    converted['phase'] = phase
                    self._maybe_log_phase_transition(promo_code, phase)
                except Exception:
                    converted['phase'] = 'Build'
                # Uploaded file metadata is now only read from disk; promo_history queries removed.
                try:
                    promo_dir = os.path.join(self.promo_uploads_dir, promo_code)
                    # Rebuild uploaded_files from disk
                    uploaded_files = {}
                    for file_type, disk_name in [('sku_excel', 'sku_list.xlsx'), ('tradein_excel', 'tradein_list.xlsx')]:
                        fpath = os.path.join(promo_dir, disk_name)
                        if os.path.exists(fpath):
                            # Try reading sidecar metadata first
                            meta_path = os.path.join(promo_dir, f"{file_type}.meta.json")
                            if os.path.exists(meta_path):
                                try:
                                    with open(meta_path, 'r', encoding='utf-8') as mf:
                                        uploaded_files[file_type] = json.load(mf)
                                    # Ensure file_path is current
                                    uploaded_files[file_type]['file_path'] = fpath
                                    continue
                                except Exception:
                                    pass
                            # Fallback: build metadata from file stats
                            stat = os.stat(fpath)
                            uploaded_files[file_type] = {
                                'filename': disk_name,
                                'original_name': disk_name,
                                'upload_date': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                'file_size': stat.st_size,
                                'file_path': fpath,
                            }
                    if uploaded_files:
                        converted['uploaded_files'] = uploaded_files

                    # Attach generated SQL content
                    sql_file_path = os.path.join(promo_dir, f"{promo_code}_promo_eligibility_rules.sql")
                    if os.path.exists(sql_file_path):
                        try:
                            with open(sql_file_path, 'r', encoding='utf-8', errors='replace') as sf:
                                sql_content = sf.read()
                            converted['generated_sql'] = sql_content
                            converted['sql_length'] = len(sql_content)
                        except Exception as read_sql_err:
                            logger.warning("Read generated SQL failed for %s: %s", promo_code, read_sql_err)
                except Exception as attach_err:
                    logger.warning("Attach uploaded_files failed for %s: %s", promo_code, attach_err)
                return converted
            return {}
        except Exception as e:
            logger.error("Database lookup failed for %s: %s", promo_code, e)
            return {}
    
    def delete_promo(self, promo_code: str) -> bool:
        """Delete promotion from database and cleanup extras/files."""
        deleted = False
        
        # Delete from main promo table
        try:
            from sqlalchemy import text
            engine = self.db_manager.get_engine()
            sql = f"DELETE FROM {self.db_manager.source_table} WHERE code = :promo_code"
            with engine.begin() as conn:
                result = conn.execute(text(sql), {'promo_code': promo_code})
                if result.rowcount > 0:
                    deleted = True
        except Exception as e:
            logger.error("[DELETE] Database deletion failed for %s: %s", promo_code, e)
        
        # Delete uploaded files
        try:
            promo_dir = os.path.join(self.promo_uploads_dir, promo_code)
            if os.path.exists(promo_dir):
                import shutil
                shutil.rmtree(promo_dir)
        except Exception as e:
            logger.warning("[DELETE] File cleanup failed for %s: %s", promo_code, e)
        
        return deleted
    
    def get_spe_promo(self, promo_code: str) -> Dict[str, Any]:
        """Fast lookup of a single SPE promo by code.

        Previous implementation fetched ALL SPE promos then iterated to find a match,
        incurring an unnecessary full table scan + conversion cost on every request.
        This optimized path issues a single parameterized query via get_promo_by_code
        and validates Desired_Execution == 'SPE'. Falls back to empty dict if not found
        or if the promo is of a different execution type.
        """
        try:
            rec = self.db_manager.get_promo_by_code(promo_code)
            if not rec:
                return {}
            # Normalize execution type key across potential case/alias differences
            exec_type = rec.get('Desired_Execution') or rec.get('desired_execution') or rec.get('execution_type')
            if str(exec_type).upper() != 'SPE':
                return {}
            return self.db_manager.convert_db_record_to_json_format({str(k): v for k,v in rec.items()})
        except Exception as e:
            logger.warning("Fast SPE lookup failed for %s: %s", promo_code, e)
            return {}
    
    def get_all_promos(self) -> Dict[str, Any]:
        """Get all promotions (RDC) from database (no JSON overlay)."""
        try:
            db_records = self.db_manager.get_promos_by_execution_type("RDC")
        except Exception as e:
            logger.error("Database lookup failed for all promos: %s", e)
            db_records = []
        result: Dict[str, Any] = {}
        for record in db_records:
            record_dict: Dict[str, Any] = {str(k): v for k, v in record.items()} if record else {}
            converted = self.db_manager.convert_db_record_to_json_format(record_dict)
            code = converted.get('code')
            if code:
                result[code] = converted
        return result
    
    def get_paginated_promos(self, page: int = 1, per_page: int = 25, search: str = "", owner_filter: str = "all") -> Dict[str, Any]:
        """Get paginated promotions with optional filtering (DB only)."""
        # Legacy (non-optimized) path kept for fallback; new optimized path below.
        try:
            db_records = self.db_manager.get_promos_by_execution_type("RDC")
        except Exception as e:
            logger.error("Database lookup failed for paginated promos: %s", e)
            db_records = []
        promo_list: List[Dict[str, Any]] = []
        for record in db_records:
            record_dict: Dict[str, Any] = {str(k): v for k, v in record.items()} if record else {}
            converted = self.db_manager.convert_db_record_to_json_format(record_dict)
            # Compute phase per promo (without logging yet; bulk logging after filters maybe expensive)
            try:
                phase = self._compute_phase(converted.get('promo_start_date'), converted.get('promo_end_date'))
            except Exception:
                phase = 'Build'
            converted['status'] = phase
            code_val = converted.get('code')
            if code_val:
                self._maybe_log_phase_transition(code_val, phase)
            promo_list.append(converted)
        
        # Apply filters
        if search:
            search_lower = (search or '').lower()
            safe_contains = []
            for promo in promo_list:
                code_val = (promo.get('code') or '')
                owner_val = (promo.get('owner') or '')
                bfname_val = (promo.get('bill_facing_name') or '')
                try:
                    if (search_lower in code_val.lower() or
                        search_lower in owner_val.lower() or
                        search_lower in bfname_val.lower()):
                        safe_contains.append(promo)
                except Exception:
                    # Skip any malformed promo dict
                    continue
            promo_list = safe_contains
        
        if owner_filter and owner_filter != "all":
            promo_list = [promo for promo in promo_list if (promo.get('owner') or '') == owner_filter]
        
        # Phase-aware ordering: upcoming (Build, soonest start first), Launched (soonest end), Expired (most recent end first at tail)
        from datetime import datetime as _dt, timezone as _tz
        today = _dt.now(_tz.utc).date()
        def parse_date(val):
            if not val:
                return None
            try:
                return _dt.strptime(val[:10], '%Y-%m-%d').date()
            except Exception:
                return None
        def sort_key(p):
            phase = p.get('status') or 'Build'
            start = parse_date(p.get('promo_start_date'))
            end = parse_date(p.get('promo_end_date'))
            if phase == 'Build':
                # Days until start (None treated as large number to push unknown further down within Build)
                delta = (start - today).days if start else 99999
                return (0, delta, start or today, p.get('code'))
            if phase == 'Launched':
                # Days until end ascending
                remaining = (end - today).days if end else 99999
                return (1, remaining, end or today, p.get('code'))
            # Expired: days since end ascending but group placed last
            since = (today - end).days if end else 99999
            return (2, since, end or today, p.get('code'))
        promo_list.sort(key=sort_key)
        
        # Calculate pagination
        total_items = len(promo_list)
        total_pages = (total_items + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        
        paginated_promos = promo_list[start:end]
        
        # Get unique owners for filter dropdown
        all_owners = sorted(set(promo.get('owner', '') for promo in promo_list if promo.get('owner')))
        
        return {
            'promotions': paginated_promos,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_items,
                'total_pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'prev_num': page - 1 if page > 1 else None,
                'next_num': page + 1 if page < total_pages else None
            },
            'owners': all_owners
        }

    # Backwards-compatible wrapper expected by some routes (previous hybrid storage API)
    def get_pam_only_paginated_promos(self, page: int = 1, per_page: int = 25, search: str = "", owner_filter: str = "all") -> Dict[str, Any]:
        """Alias to get_paginated_promos retained so existing route checks succeed."""
        return self.get_paginated_promos(page=page, per_page=per_page, search=search, owner_filter=owner_filter)

    # Optimized path leveraging DB-side filtering/pagination
    def get_paginated_promos_optimized(self, page: int = 1, per_page: int = 25, search: str = "", owner_filter: str = "all", scope: str = "all") -> Dict[str, Any]:
        data = self.db_manager.get_paginated_execution_type(
            execution_type="RDC",
            page=page,
            per_page=per_page,
            search=search,
            owner_filter=owner_filter,
            upcoming_only_when_no_query=False,
            force_upcoming=(scope == 'upcoming'),
        )
        # Compute phase only for returned rows (lightweight)
        from datetime import datetime as _dt, timezone as _tz
        today = _dt.now(_tz.utc).date()
        def parse_date(val):
            if not val:
                return None
            try:
                return _dt.strptime(val[:10], '%Y-%m-%d').date()
            except Exception:
                return None
        for promo in data['promotions']:
            start = parse_date(promo.get('promo_start_date'))
            end = parse_date(promo.get('promo_end_date'))
            if start and start > today:
                phase = 'Build'
            elif end and end < today:
                phase = 'Expired'
            else:
                phase = 'Launched'
            promo['status'] = phase
        return data

    def get_paginated_spe_promos_optimized(self, page: int = 1, per_page: int = 25, search: str = "", owner_filter: str = "all", scope: str = "all") -> Dict[str, Any]:
        """Optimized SPE listing with upcoming-only default; includes launched/expired on query."""
        data = self.db_manager.get_paginated_execution_type(
            execution_type="SPE",
            page=page,
            per_page=per_page,
            search=search,
            owner_filter=owner_filter,
            upcoming_only_when_no_query=False,
            force_upcoming=(scope == 'upcoming'),
        )
        from datetime import datetime as _dt, timezone as _tz
        today = _dt.now(_tz.utc).date()
        def parse_date(val):
            if not val:
                return None
            try:
                return _dt.strptime(val[:10], '%Y-%m-%d').date()
            except Exception:
                return None
        for promo in data['promotions']:
            start = parse_date(promo.get('promo_start_date'))
            end = parse_date(promo.get('promo_end_date'))
            if start and start > today:
                phase = 'Build'
            elif end and end < today:
                phase = 'Expired'
            else:
                phase = 'Launched'
            promo['status'] = phase
        return data
    
    def get_all_spe_promos(self) -> Dict[str, Any]:
        """Get all SPE promotions (DB)."""
        out: Dict[str, Any] = {}
        try:
            for r in self.db_manager.get_promos_by_execution_type("SPE"):
                conv = self.db_manager.convert_db_record_to_json_format({str(k): v for k,v in r.items()})
                c = conv.get('code')
                if c:
                    out[c] = conv
        except Exception as e:
            logger.warning("get_all_spe_promos failed: %s", e)
        return out

    def save_promo(self, promo_code: str, promo_data: Dict[str, Any], user_name: str = "System"):
        """Persist promo edits: update PAM table fields, upsert extras, record diff version history."""
        promo_data = dict(promo_data or {})
        promo_data['code'] = promo_code

        # 1. Fetch current state (base + extras)
        try:
            base_record = self.db_manager.get_promo_by_code(promo_code) or {}
        except Exception:
            base_record = {}
        is_new_promo = not bool(base_record)

        if not base_record:
            # Attempt minimal creation (Orbit-less) for test harness / admin utilities.
            try:
                minimal_fields = {
                    'code': promo_code,
                    'description': promo_data.get('description',''),
                    'Owner': promo_data.get('Owner') or promo_data.get('owner',''),
                    'promo_start_date': promo_data.get('promo_start_date') or datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                    'promo_end_date': promo_data.get('promo_end_date') or datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                    'Desired_Execution': promo_data.get('Desired_Execution') or 'RDC'
                }
                inserted = self.db_manager.insert_minimal_promo(minimal_fields, user=user_name)
                if inserted:
                    base_record = self.db_manager.get_promo_by_code(promo_code) or {}
                else:
                    return {'success': False, 'changed': [], 'diff': {}, 'error': 'Base promo not found (creation failed)'}
            except Exception:
                return {'success': False, 'changed': [], 'diff': {}, 'error': 'Base promo not found (creation error)'}

        # Editable canonical fields come from shared field_map
        base_editable_fields = set(EDITABLE_CANONICAL_FIELDS)
        # Legacy synonyms that may arrive from UI posts; map them to canonical columns if encountered.
        synonym_map = {
            'flow_indicator': 'flow_ind',  # UI may still send old name
            'jira_ticket': 'dcd_jira',
            'trade_in_grp_id': 'trade_in_group_id',  # normalize short form
            'tiered_group_id': 'tiered_grp_id',      # normalize to grp variant per CSV
            'broken_trade': 'Broken_Trade',          # UI lowercase -> DB camel/pascal
            # Tiered promo tiers (UI tier_X_* -> promo_tier_X_*)
            'tier_1_amount': 'promo_tier_1_amount',
            'tier_1_sku_group_id': 'promo_tier_1_sku_group_id',
            'tier_1_devices': 'promo_tier_1_devices',
            'tier_2_amount': 'promo_tier_2_amount',
            'tier_2_sku_group_id': 'promo_tier_2_sku_group_id',
            'tier_2_devices': 'promo_tier_2_devices',
            'tier_3_amount': 'promo_tier_3_amount',
            'tier_3_sku_group_id': 'promo_tier_3_sku_group_id',
            'tier_3_devices': 'promo_tier_3_devices',
            # Trade tiers (UI trade_tier_X_* -> mk_mdl_grp_tier_X_* canonical)
            'trade_tier_1_make_model': 'mk_mdl_grp_tier_1',
            'trade_tier_1_amount': 'mk_mdl_grp_tier_1_amount',
            'trade_tier_1_cond_id': 'mk_mdl_grp_tier_1_condition_id',
            'trade_tier_1_min_fmv': 'mk_mdl_grp_tier_1_min_fmv',
            'trade_tier_1_max_fmv': 'mk_mdl_grp_tier_1_max_fmv',
            'trade_tier_2_make_model': 'mk_mdl_grp_tier_2',
            'trade_tier_2_amount': 'mk_mdl_grp_tier_2_amount',
            'trade_tier_2_cond_id': 'mk_mdl_grp_tier_2_condition_id',
            'trade_tier_2_min_fmv': 'mk_mdl_grp_tier_2_min_fmv',
            'trade_tier_2_max_fmv': 'mk_mdl_grp_tier_2_max_fmv',
            'trade_tier_3_make_model': 'mk_mdl_grp_tier_3',
            'trade_tier_3_amount': 'mk_mdl_grp_tier_3_amount',
            'trade_tier_3_cond_id': 'mk_mdl_grp_tier_3_condition_id',
            'trade_tier_3_min_fmv': 'mk_mdl_grp_tier_3_min_fmv',
            'trade_tier_3_max_fmv': 'mk_mdl_grp_tier_3_max_fmv',
            'trade_tier_4_make_model': 'mk_mdl_grp_tier_4',
            'trade_tier_4_amount': 'mk_mdl_grp_tier_4_amount',
            'trade_tier_4_cond_id': 'mk_mdl_grp_tier_4_condition_id',
            'trade_tier_4_min_fmv': 'mk_mdl_grp_tier_4_min_fmv',
            'trade_tier_4_max_fmv': 'mk_mdl_grp_tier_4_max_fmv',
        }

        # Normalize incoming promo_data keys based on synonym_map
        normalized_promo_data = {}
        for k,v in promo_data.items():
            target_key = synonym_map.get(k, k)
            normalized_promo_data[target_key] = v
        promo_data = normalized_promo_data

        # Validation / sanitization (lightweight) before partitioning
        def _sanitize(key: str, value: Any) -> Any:
            if key == 'bptcr':
                # Expect 5 numeric characters; strip non-digits and enforce length
                import re
                digits = ''.join(re.findall(r'\d', str(value)))
                return digits[:5] if len(digits) >= 5 else digits  # keep partial rather than blank to allow user correction UI-side
            return value

        base_updates = {}
        for k,v in promo_data.items():
            if k in base_editable_fields:
                base_updates[k] = _sanitize(k, v)

        # 3. Compute old unified snapshot for diff
        unified_before = {}
        for k in base_editable_fields:
            unified_before[k] = base_record.get(k)

        # 4. Apply updates
        if base_updates:
            self.db_manager.update_promo_fields(promo_code, base_updates)

        # 5. Fetch after state for diff
        try:
            new_base = self.db_manager.get_promo_by_code(promo_code) or {}
        except Exception:
            new_base = {}
        unified_after = {}
        for k in base_editable_fields:
            unified_after[k] = new_base.get(k)

        # 6. Diff
        diff = {}
        changed_fields = []
        for k in sorted(set(unified_before.keys()) | set(unified_after.keys())):
            before_val = unified_before.get(k)
            after_val = unified_after.get(k)
            if before_val != after_val:
                diff[k] = {'old': before_val, 'new': after_val}
                changed_fields.append(k)

                if changed_fields:
                    human_list = ', '.join(changed_fields[:10]) + ('...' if len(changed_fields) > 10 else '')
                    description = f"Edited fields: {human_list}"
                    _ = description

        # 7. Version history events
        if is_new_promo:
            created_snapshot = {
                'orbit_id': (new_base.get('orbit_id') if new_base else None) or promo_data.get('orbit_id'),
                'promo_code': promo_code,
                'promo_owner': (new_base.get('Owner') if new_base else None) or promo_data.get('Owner') or promo_data.get('owner'),
                'promo_type': (new_base.get('Desired_Execution') if new_base else None) or promo_data.get('Desired_Execution') or promo_data.get('promo_type')
            }
            log_version_event(
                promo_code=promo_code,
                promo_id=promo_code,
                orbit_id=created_snapshot.get('orbit_id'),
                promo_owner=created_snapshot.get('promo_owner'),
                promo_type=created_snapshot.get('promo_type'),
                event_type='created',
                actor=user_name,
                source='save_promo',
                created_snapshot=created_snapshot
            )
        elif changed_fields:
            changed_payload = {
                k: {'from': diff[k].get('old'), 'to': diff[k].get('new')}
                for k in changed_fields
            }
            log_version_event(
                promo_code=promo_code,
                promo_id=promo_code,
                orbit_id=new_base.get('orbit_id') if new_base else None,
                promo_owner=new_base.get('Owner') if new_base else None,
                promo_type=new_base.get('Desired_Execution') if new_base else None,
                event_type='modified',
                actor=user_name,
                source='save_promo',
                changed_fields=changed_payload
            )

        return {
            'success': True,
            'changed': changed_fields,
            'diff': diff,
            'applied_base_fields': list(base_updates.keys()),
        }

    # Version history functionality removed from this manager entirely.
    
    def save_spe_promo(self, promo_code: str, promo_data: Dict[str, Any], user_name: str = "System"):
        """Save or update an SPE promotion with change tracking"""
        data = self._load_json(self.spe_file)
        
        # Add metadata
        promo_data['code'] = promo_code
        promo_data['updated_at'] = datetime.now().isoformat()
        
        # If it's a new promo, add creation timestamp
        if promo_code not in data:
            promo_data['created_at'] = datetime.now().isoformat()
            # Version history removed: do not persist version history entries
            promo_data['last_changes'] = None
        else:
            # Preserve creation timestamp and existing permanent version history
            old_data = data[promo_code]
            promo_data['created_at'] = old_data.get('created_at', datetime.now().isoformat())
            
            # Version history removed: do not copy over old version_history
            
            # Track field changes
            changes = self._get_field_changes(old_data, promo_data)
            if changes:
                # Update last_changes with current change summary
                timestamp = datetime.now().strftime('%m/%d/%Y %I:%M %p')
                change_summary = f"Last save: {timestamp} - {user_name} - Changed: {', '.join(changes)}"
                promo_data['last_changes'] = change_summary
            else:
                # Keep existing last_changes if no actual field changes
                promo_data['last_changes'] = old_data.get('last_changes')
        
        data[promo_code] = promo_data
        self._save_json(self.spe_file, data)
    
    def _get_field_changes(self, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> List[str]:
        """Compare old and new data to find changed fields"""
        changes = []
        
        # Fields to track for changes (excluding metadata and system fields)
        tracked_fields = {
            'bill_facing_name': 'Bill Facing Name',
            'discount': 'Promo % Discount', 
            'amount': 'Promo Amount',
            'nseip_drop': 'NSEIP Drop',
            'dcd_web_cart': 'DCD Web Cart',
            'product_type': 'Product Type',
            'bogo': 'BOGO',
            'trade_in_group_id': 'Trade-In Group ID',
            'fpd_display_promo': 'FPD Display Promo',
            'on_menu': 'On Menu',
            'market_group': 'Market Group',
            'store_group': 'Store Group',
            'sku_link': 'SKU Link',
            'tradein_link': 'Trade-In Link',
            'promo_start_date': 'Promo Start Date',
            'promo_end_date': 'Promo End Date',
            'comm_end_date': 'Comm End Date',
            'promo_duration': 'Promo Duration',
            'delay_time': 'Delay Time',
            'application_grace_period': 'Application Grace Period',
            'promo_grace': 'Promo Grace',
            'trade_in_grace': 'Trade-In Grace',
            'mpss_lookback': 'MPSS Lookback',
            'device_sales_type': 'Device Sales Type',
            'activation_type': 'Activation Type',
            'maintain_soc': 'Maintain SOC',
            'limit_per_ban': 'Limit Per BAN',
            'min_gsm_count': 'Min GSM Count',
            'max_gsm_count': 'Max GSM Count',
            'port_in_group_id': 'Port-In Group ID',
            'segment_name': 'Segment Name',
            'sub_segment': 'Sub Segment',
            'segment_group_id': 'Segment Group ID',
            'segment_level': 'Segment Level',
            'soc_grouping': 'SOC Grouping',
            'account_type': 'Account Type',
            'sales_application': 'Sales Application',
            'bptcr': 'BPTCR',
            'jira_ticket': 'JIRA Ticket',
            # SPE specific fields
            'promo_identifier': 'Promo Identifier',
            'pt_priority_indicator': 'PT Priority Indicator',
            'service_priority': 'Service Priority',
            'max_discount': 'Max Discount',
            'c2_content': 'C2 Content',
            'pr_date': 'PR Date',
            'ban_tenure_start': 'BAN Tenure Start',
            'ban_tenure_end': 'BAN Tenure End',
            'maintain_line_count_days': 'Maintain Line Count Days',
            're_enroll_period': 'Re-enroll Period',
            'port_duration': 'Port Duration',
            'channel_grace_period': 'Channel Grace Period',
            'tfb_channel_group_id': 'TFB Channel Group ID',
            'dealer_group_id': 'Dealer Group ID',
            'updated_mrc_ranking': 'Updated MRC Ranking',
            'suppress_discount_reorder': 'Suppress Discount Reorder',
            'retro_ban_evaluation': 'Retro BAN Evaluation',
            'adjustment_code': 'Adjustment Code',
            'discount_codes': 'Discount Codes',
            'total_indicator': 'Total Indicator',
            'gsm_indicator': 'GSM Indicator',
            'mi_indicator': 'MI Indicator',
            'pure_mi_indicator': 'Pure MI Indicator',
            'virtual_mi_indicator': 'Virtual MI Indicator',
            'duplicate_indicator': 'Duplicate Indicator',
            'auto_att_indicator': 'Auto Att Indicator',
            'fax_line_indicator': 'Fax Line Indicator',
            'conference_indicator': 'Conference Indicator',
            'iot_indicator': 'IOT Indicator',
            'go_soc_group_id': 'GO SOC Group ID',
            'bo_soc_group_id': 'BO SOC Group ID',
            'paid_soc_group_id': 'Paid SOC Group ID',
            'min_paid_line_mi_count': 'Min Paid Line MI Count',
            'go_line_maintenance': 'GO Line Maintenance',
            'bo_line_maintenance': 'BO Line Maintenance',
            'paid_line_maintenance': 'Paid Line Maintenance',
            'min_paid_line_gsm_count': 'Min Paid Line GSM Count',
            'go_line_count': 'GO Line Count',
            'bo_line_count': 'BO Line Count',
            'borrow_bo_lines': 'Borrow BO Lines',
            'lend_bo_lines': 'Lend BO Lines',
            'soc_discount_mapping': 'SOC Discount Mapping'
        }
        
        for field, display_name in tracked_fields.items():
            old_value = old_data.get(field)
            new_value = new_data.get(field)
            
            # Normalize values for comparison (handle None, empty strings, etc.)
            old_normalized = self._normalize_value(old_value)
            new_normalized = self._normalize_value(new_value)
            
            if old_normalized != new_normalized:
                # Format the change description
                if new_normalized == '':
                    changes.append(f"{display_name} (cleared)")
                else:
                    changes.append(f"{display_name} (→ {new_normalized})")
        
        return changes
    
    def _normalize_value(self, value: Any) -> str:
        """Normalize a value for comparison"""
        if value is None:
            return ''
        if isinstance(value, str):
            return value.strip()
        return str(value)
    
    # Version history methods removed

    # --- Creation / Orbit ingestion helpers ---
    def _generate_next_sequential_code(self) -> str:
        """Generate next sequential promo code using DB + issued tombstones.

        Pattern: Letter + 3-4 digits. R001 seeded if none. Rolls numeric then letter.
        """
        from data.code_tracking import load_issued_codes, record_issued_code
        issued = load_issued_codes()
        highest = self.db_manager.get_highest_sequential_promo_code()
        import re
        pat = re.compile(r'^([A-Z])(\d{1,4})$')
        if not highest:
            letter = 'R'; num = 1
        else:
            m = pat.match(highest.upper())
            if not m:
                letter = 'R'; num = 1
            else:
                letter = m.group(1)
                num = int(m.group(2)) + 1
                if num > 9999:
                    if letter == 'Z':
                        raise RuntimeError('Exhausted promo code namespace')
                    letter = chr(ord(letter)+1)
                    num = 1
        while True:
            width = 3 if num <= 999 else 4
            candidate = f"{letter}{num:0{width}d}"
            if candidate not in issued:
                record_issued_code(candidate)
                return candidate
            num += 1

    def create_promo_from_orbit(self, orbit_id: str, desired_execution: str = 'RDC', user_name: str = 'System') -> Dict[str, Any]:
        """Create a new promo by ingesting an Orbit record (by orbit_id) and assigning a fresh promo code.

        Steps:
          1. Validate orbit_id not already assigned.
          2. Fetch orbit row (full) via DatabaseManager.
          3. Generate next code.
          4. Insert row into PAM source table with essential columns.
          5. Record version history 'Created'.
          6. Return converted JSON format payload.
        """
        orbit_id_clean = (orbit_id or '').strip()
        if not orbit_id_clean:
            return {'success': False, 'error': 'orbit_id required'}
        # Ensure not already present
        for rec in self.db_manager.get_all_promotions_unified():
            if str(rec.get('orbit_id','')) == orbit_id_clean:
                return {'success': False, 'error': 'Orbit already assigned', 'existing_code': rec.get('code')}
        orbit_row = self.db_manager.get_full_orbit_record_by_orbit_id(orbit_id_clean)
        if not orbit_row:
            return {'success': False, 'error': f'Orbit {orbit_id_clean} not found'}
        new_code = self._generate_next_sequential_code()
        # Minimal insertion map (copy key fields; rely on later edits for others)
        insertion_fields = {
            'code': new_code,
            'orbit_id': orbit_id_clean,
            'description': orbit_row.get('description') or orbit_row.get('bill_facing_name') or f'Orbit {orbit_id_clean}',
            'bill_facing_name': orbit_row.get('bill_facing_name') or orbit_row.get('description'),
            'initiative_name': orbit_row.get('initiative_name') or '',
            'Owner': orbit_row.get('Owner') or 'Unassigned',
            'promo_start_date': orbit_row.get('promo_start_date'),
            'promo_end_date': orbit_row.get('promo_end_date'),
            'Desired_Execution': desired_execution
        }
        # Include optional known columns if present in orbit_row
        for opt in ['amount','discount','sku_group_id','device_status_group_id','soc_grouping','account_type','sales_application','application_grace_period']:
            if opt in orbit_row and orbit_row.get(opt) is not None:
                insertion_fields[opt] = orbit_row.get(opt)
        ok = self.db_manager.insert_promo_record(insertion_fields)
        if not ok:
            return {'success': False, 'error': 'Insert failed'}
        # Version history storage removed; creation events are not recorded.
        # Return unified converted record
        db_record = self.db_manager.get_promo_by_code(new_code) or {}
        payload = self.db_manager.convert_db_record_to_json_format(db_record)
        payload['success'] = True
        return payload
    
    # --- Phase computation helpers ---
    @staticmethod
    def _compute_phase(start_date: Optional[str], end_date: Optional[str], now: Optional[datetime] = None) -> str:
        """Compute phase: Build, Launched, Expired.

        Rules:
          - Build: now < start_date OR start_date missing
          - Launched: start_date <= now AND (end_date missing OR now <= end_date)
          - Expired: end_date < now (strictly; i.e., expires only after end date passes)

        Dates are date-only strings YYYY-MM-DD. If unparsable, treat as missing.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        def parse(d: Optional[str]):
            if not d:
                return None
            try:
                return datetime.strptime(str(d)[:10], "%Y-%m-%d")
            except Exception:
                return None
        s = parse(start_date)
        e = parse(end_date)
        today = datetime(year=now.year, month=now.month, day=now.day)
        # Expired: only if we have an end date and today > end
        if e is not None and today > e:
            return 'Expired'
        # Build: before start OR start missing (and not expired)
        if s is None or today < s:
            return 'Build'
        # Launched: started and not expired (end missing or today <= end)
        return 'Launched'

    def delete_spe_promo(self, promo_code: str):
        """Delete an SPE promotion"""
        data = self._load_json(self.spe_file)
        if promo_code in data:
            del data[promo_code]
            self._save_json(self.spe_file, data)
    
    def get_promo_list(self) -> List[Dict[str, Any]]:
        """Get a list of all promotions (DB only)."""
        all_promos = self.get_all_promos()
        now = datetime.now(timezone.utc)
        rows: List[Dict[str, Any]] = []
        for code, promo in all_promos.items():
            start_date = promo.get('promo_start_date') or ''
            end_date = promo.get('promo_end_date') or ''
            phase = self._compute_phase(start_date, end_date, now)
            rows.append({
                'code': code,
                'orbit_id': promo.get('orbit_id', ''),
                'status': phase,
                'description': promo.get('description', ''),
                'start_date': promo.get('promo_start_date', ''),
                'end_date': end_date,
                'owner': promo.get('owner', ''),
                'type': 'RDC'
            })
        return rows
    
    def get_spe_promo_list(self) -> List[Dict[str, Any]]:
        """DB list of all SPE promotions for display."""
        items: List[Dict[str, Any]] = []
        now_str = datetime.now().strftime("%Y-%m-%d")
        try:
            for r in self.db_manager.get_promos_by_execution_type("SPE"):
                end_date = r.get('promo_end_date','')
                items.append({
                    'code': r.get('code',''),
                    'orbit_id': r.get('orbit_id',''),
                    'status': 'Active' if (end_date and str(end_date) > now_str) else 'Expired',
                    'description': r.get('description',''),
                    'start_date': r.get('promo_start_date',''),
                    'end_date': end_date,
                    'owner': r.get('Owner',''),
                    'type': 'SPE'
                })
        except Exception:
            pass
        return items
    
    def get_rebate_list(self) -> List[Dict[str, Any]]:
        """DB list of all rebate promotions for display."""
        items: List[Dict[str, Any]] = []
        now_str = datetime.now().strftime("%Y-%m-%d")
        try:
            for r in self.db_manager.get_promos_by_execution_type("Rebate"):
                end_date = r.get('promo_end_date','')
                items.append({
                    'code': r.get('code',''),
                    'orbit_id': r.get('orbit_id',''),
                    'status': 'Active' if (end_date and str(end_date) > now_str) else 'Expired',
                    'description': r.get('description',''),
                    'start_date': r.get('promo_start_date',''),
                    'end_date': end_date,
                    'owner': r.get('Owner',''),
                    'type': 'REBATE'
                })
        except Exception:
            pass
        return items

    def get_all_rebates(self) -> Dict[str, Any]:
        """Get all rebates (DB)."""
        out: Dict[str, Any] = {}
        try:
            for r in self.db_manager.get_promos_by_execution_type("Rebate"):
                conv = self.db_manager.convert_db_record_to_json_format({str(k): v for k,v in r.items()})
                c = conv.get('code') or conv.get('promo_code')
                if c:
                    out[c] = conv
        except Exception:
            pass
        return out
    
    def get_owners(self) -> List[str]:
        """Owners across all execution types from DB."""
        owners = set()
        try:
            for r in self.db_manager.get_all_promotions_unified():
                o = r.get('Owner') or r.get('owner')
                if o:
                    owners.add(o)
        except Exception:
            pass
        return ["All"] + sorted(owners)
    
    def get_soc_groupings(self) -> list:
        """Return the exact list of SOC grouping codes for the dropdown."""
        return [
            "10B", "10C", "15A", "15N", "15S", "17D", "1AS", "1NS", "2AS", "2NS",
            "69N", "69S", "A3N", "A6N", "A6S", "A7N", "A7S", "A8N", "A8R", "A8S",
            "ALL", "AN8", "AR3", "AR6", "AR7", "AR8", "AT1", "AT2", "AT3", "AT4",
            "AT5", "AT6", "AT7", "B1", "B10", "B11", "B2", "B3", "B4", "B5",
            "B6", "B7", "B8", "B9", "G03", "G04", "G05", "G06", "G07", "G08",
            "G09", "G10", "G11", "G12", "G13", "G14", "G15", "G16", "G17", "G18",
            "G19", "G20", "G21", "G22", "G23", "G24", "G25", "G26", "G27", "G28",
            "G29", "G30", "G31", "G32", "G33", "G34", "G35", "G36", "G37", "G38",
            "G39", "G40", "G41", "G42", "G43", "G44", "G45", "G46", "G47", "G48",
            "G49", "G50", "G51", "G52", "G53", "G54", "G55", "G56", "G57", "G58",
            "G59", "G60", "G61", "G62", "G63", "G64", "G65", "G66", "G67", "G68",
            "G69", "G70", "G71", "G72", "G73", "G74", "G75", "G76", "G77", "G78",
            "G79", "G7A", "G80", "G81", "G82", "G99", "G9A", "TB1", "W1", "W10",
            "W12", "W13", "W1N", "W1S", "W2", "W3", "W3N", "W4", "W5", "W6",
            "W7", "W7N", "W7S", "W8", "W8N", "W8S", "W9", "WN8", "WR8"
        ]
    
    def get_soc_grouping_details(self) -> str:
        """Return formatted HTML with CODE - LABEL and bullet list of items using standardized pipe format."""
        soc_file_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'soc_grouping.txt')
        try:
            if not os.path.exists(soc_file_path):
                return "SOC Grouping file not found."
            out_blocks = []
            with open(soc_file_path, 'r', encoding='utf-8') as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith('#'):
                        continue
                    # Expect CODE|LABEL|items
                    parts = line.split('|')
                    if len(parts) < 2:
                        continue
                    code = parts[0].strip()
                    label = parts[1].strip()
                    items_part = parts[2].strip() if len(parts) > 2 else ''
                    block = [f"<div class='grouping-row'><div class='grouping-head'><strong>{code}</strong> - {label}</div>"]
                    if items_part:
                        items = [i.strip() for i in items_part.split(',') if i.strip()]
                        if items:
                            block.append("<ul class='grouping-items'>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
                    block.append("</div>")
                    out_blocks.append("".join(block))
            return "".join(out_blocks) or "No SOC groupings found"
        except Exception as e:
            return f"Error reading SOC groupings: {e}"
    
    def get_account_types(self) -> List[str]:
        """Get list of account type codes from account_types.txt"""
        return [
            "A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10",
            "A11", "A12", "A13", "A14", "A15", "A16", "A17", "ALL", "AT1", "AT2",
            "AT3", "AT4", "AT5", "AT6", "AT7", "GST"
        ]
    
    def get_account_type_details(self) -> str:
        """Return formatted HTML for account types using standardized pipe format."""
        try:
            account_types_file = os.path.join(os.path.dirname(__file__), '..', 'static', 'account_types.txt')
            if not os.path.exists(account_types_file):
                return "Account Types file not found."
            out_blocks = []
            with open(account_types_file, 'r', encoding='utf-8') as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split('|')
                    if len(parts) < 2:
                        continue
                    code = parts[0].strip()
                    label = parts[1].strip()
                    items_part = parts[2].strip() if len(parts) > 2 else ''
                    block = [f"<div class='grouping-row'><div class='grouping-head'><strong>{code}</strong> - {label}</div>"]
                    if items_part:
                        items = [i.strip() for i in items_part.split(',') if i.strip()]
                        if items:
                            block.append("<ul class='grouping-items'>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
                    block.append("</div>")
                    out_blocks.append("".join(block))
            return "".join(out_blocks) or "No account types found"
        except Exception as e:
            return f"Error reading account types: {e}"
    
    def get_sales_applications(self) -> List[str]:
        """Get list of sales application codes from sales_apps.txt"""
        try:
            sales_apps_file = os.path.join(os.path.dirname(__file__), '..', 'static', 'sales_apps.txt')
            
            with open(sales_apps_file, 'r', encoding='utf-8') as file:
                content = file.read().strip()
            
            if not content:
                return []
            
            codes: List[str] = []
            for raw in content.split('\n'):
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                # Standard pipe format CODE|LABEL|ITEMS (ITEMS optional)
                parts = line.split('|')
                if not parts:
                    continue
                code = parts[0].strip()
                if code:
                    codes.append(code)
            return codes
        except FileNotFoundError:
            logger.warning("sales_apps.txt file not found.")
            return []
        except Exception as e:
            logger.error("Error reading sales applications: %s", e)
            return []
    
    def get_sales_application_details(self) -> str:
        """Return formatted HTML for sales applications using standardized pipe format."""
        try:
            sales_apps_file = os.path.join(os.path.dirname(__file__), '..', 'static', 'sales_apps.txt')
            if not os.path.exists(sales_apps_file):
                return "Sales Applications file not found."
            out_blocks = []
            with open(sales_apps_file, 'r', encoding='utf-8') as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split('|')
                    if len(parts) < 2:
                        continue
                    code = parts[0].strip()
                    label = parts[1].strip() if len(parts) > 1 else ''
                    items_part = parts[2].strip() if len(parts) > 2 else ''
                    block_parts = ["<div class='grouping-row'>"]
                    # Build head: CODE plus optional label
                    if label:
                        block_parts.append(f"<div class='grouping-head'><strong>{code}</strong> - {label}</div>")
                    else:
                        block_parts.append(f"<div class='grouping-head'><strong>{code}</strong></div>")
                    # Items list
                    if items_part:
                        items = [i.strip() for i in items_part.split(',') if i.strip()]
                        if items:
                            block_parts.append("<ul class='grouping-items'>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
                    block_parts.append("</div>")
                    out_blocks.append("".join(block_parts))
            return "".join(out_blocks) or "No sales applications found"
        except Exception as e:
            return f"Error reading sales applications: {e}"
    
    # File Upload Methods
    
    def _get_promo_upload_dir(self, promo_code: str) -> str:
        """Get upload directory for a specific promotion"""
        promo_dir = os.path.join(self.promo_uploads_dir, promo_code)
        os.makedirs(promo_dir, exist_ok=True)
        return promo_dir
    
    def _validate_excel_file(self, file: FileStorage) -> bool:
        """Validate uploaded file is an Excel file"""
        if not file or not file.filename:
            return False
        
        filename = file.filename.lower()
        allowed_extensions = {'.xlsx', '.xls'}
        return any(filename.endswith(ext) for ext in allowed_extensions)
    def save_excel_file(self, promo_code: str, file: FileStorage, file_type: str) -> Optional[Dict[str, Any]]:
        """
        Save uploaded Excel file for a promotion
        
        Args:
            promo_code: The promotion code
            file: The uploaded file
            file_type: Either 'sku_excel' or 'tradein_excel'
            
        Returns:
            File metadata dict or None if save failed
        """
        if not self._validate_excel_file(file):
            raise ValueError("Invalid file type. Only .xlsx and .xls files are allowed.")
        
        # Get upload directory for this promotion
        upload_dir = self._get_promo_upload_dir(promo_code)
        
        # Create secure filename
        original_filename = file.filename
        if not original_filename:
            raise ValueError("File must have a filename")
        secure_name = secure_filename(original_filename)
        
        # Set standard filename based on type
        if file_type == 'sku_excel':
            filename = 'sku_list.xlsx'
        elif file_type == 'tradein_excel':
            filename = 'tradein_list.xlsx'
        else:
            raise ValueError("Invalid file type. Must be 'sku_excel' or 'tradein_excel'")
        
        file_path = os.path.join(upload_dir, filename)
        
        # Save the file
        try:
            file.save(file_path)
            file_size = os.path.getsize(file_path)
            # Compute checksum
            import hashlib
            h = hashlib.md5()
            with open(file_path, 'rb') as fh:
                for chunk in iter(lambda: fh.read(8192), b''):
                    h.update(chunk)
            checksum = h.hexdigest()
            file_metadata = {
                "filename": filename,
                "original_name": original_filename,
                "upload_date": datetime.now().isoformat(),
                "file_size": file_size,
                "file_path": file_path,
                "checksum": checksum
            }
            # Persist metadata sidecar so original_name survives reload
            meta_path = os.path.join(upload_dir, f"{file_type}.meta.json")
            try:
                with open(meta_path, 'w', encoding='utf-8') as mf:
                    json.dump(file_metadata, mf, indent=2, ensure_ascii=False)
            except Exception:
                pass  # non-critical; disk file still present
            # File metadata tracking removed per version history deletion
            return file_metadata
            
        except Exception as e:
            # Clean up file if save failed
            if os.path.exists(file_path):
                os.remove(file_path)
            raise Exception(f"Failed to save file: {str(e)}")

    def save_sql_file(self, promo_code: str, sql_content: str, filename: str) -> str:
        """
        Save generated SQL file for a promotion
        
        Args:
            promo_code: The promotion code
            sql_content: The SQL statement content
            filename: The filename for the SQL file
            
        Returns:
            File path of the saved SQL file
        """
        # Get upload directory for this promotion
        upload_dir = self._get_promo_upload_dir(promo_code)
        
        # Create secure filename
        secure_name = secure_filename(filename)
        if not secure_name.endswith('.sql'):
            secure_name += '.sql'
        
        file_path = os.path.join(upload_dir, secure_name)
        
        # Save the SQL content to file
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(sql_content)
            size_bytes = os.path.getsize(file_path)
            import hashlib
            h = hashlib.md5(sql_content.encode('utf-8'))
            checksum = h.hexdigest()
            # upload metadata recording removed per repo-wide history removal
            return file_path
            
        except Exception as e:
            # Clean up file if save failed
            if os.path.exists(file_path):
                os.remove(file_path)
            raise Exception(f"Failed to save SQL file: {str(e)}")
    
    def get_uploaded_file_info(self, promo_code: str, file_type: str) -> Optional[Dict[str, Any]]:
        """Get information about an uploaded file"""
        promo_data = self.get_promo(promo_code)
        if not promo_data:
            return None
        
        uploaded_files = promo_data.get('uploaded_files', {})
        file_info = uploaded_files.get(file_type)
        
        if file_info and os.path.exists(file_info.get('file_path', '')):
            return file_info
        
        return None
    
    def delete_uploaded_file(self, promo_code: str, file_type: str) -> bool:
        """Delete an uploaded file"""
        try:
            promo_data = self.get_promo(promo_code)
            if not promo_data:
                return False
            
            uploaded_files = promo_data.get('uploaded_files', {})
            file_info = uploaded_files.get(file_type)
            
            if file_info and 'file_path' in file_info:
                file_path = file_info['file_path']
                if os.path.exists(file_path):
                    os.remove(file_path)
                # Also remove metadata sidecar
                meta_path = os.path.join(os.path.dirname(file_path), f"{file_type}.meta.json")
                if os.path.exists(meta_path):
                    os.remove(meta_path)
                # No need to call save_promo; uploaded_files rebuilt dynamically
            return True
        except Exception:
            return False
    
    def get_file_path(self, promo_code: str, file_type: str) -> Optional[str]:
        """Get the file path for an uploaded file"""
        file_info = self.get_uploaded_file_info(promo_code, file_type)
        if file_info:
            return file_info.get('file_path')
        return None
    
    def get_date_mismatched_promos(self) -> Dict[str, Any]:
        """Compare ORBIT (from Fabric/OrbitDatabaseManager) vs PAM (updated table) end dates.

        ORBIT end date comes from OrbitDatabaseManager (Fabric if enabled, or local SQL fallback).
        PAM end date comes from the primary source table (self.get_all_promos()).
        If JSON overlay edits existed they would be merged already in get_all_promos(); for now DB is primary.
        """
        try:
            # 1. Fetch PAM view of promos (includes updated end date)
            pam_promos = self.get_all_promos()  # returns dict code->promo
        except Exception:
            pam_promos = {}

        # 2. Collect orbit_ids for lookup
        orbit_ids = []
        code_to_orbit = {}
        for code, data in pam_promos.items():
            oid = data.get('orbit_id') or ''
            if oid:
                orbit_ids.append(str(oid))
                code_to_orbit[code] = str(oid)

        # 3. Batch fetch original ORBIT dates (raw intake table). Returns orbit_end_date per orbit_id.
        try:
            orbit_map = self.db_manager.get_orbit_dates_map(orbit_ids)
        except Exception:
            orbit_map = {}

        owners: set[str] = set()
        entries: List[Dict[str, Any]] = []
        def _norm(date_str: str) -> str:
            if not date_str:
                return ''
            s = str(date_str).strip()
            from datetime import datetime
            # Try multiple input formats; output ISO yyyy-mm-dd
            fmts = [
                '%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S'
            ]
            for f in fmts:
                try:
                    dt = datetime.strptime(s, f)
                    return dt.strftime('%Y-%m-%d')
                except Exception:
                    continue
            return s  # fallback (leave as-is if unparsable)

        for code, promo in pam_promos.items():
            pam_end = promo.get('promo_end_date', '')
            pam_start = promo.get('promo_start_date', '') or promo.get('promo_start_date','')  # legacy column
            orbit_id = code_to_orbit.get(code, '')
            orbit_dates = orbit_map.get(orbit_id, {}) if orbit_id else {}
            orbit_end = orbit_dates.get('orbit_end_date', '')
            orbit_start = orbit_dates.get('orbit_start_date', '') or pam_start  # fallback

            # Normalize ORBIT dates to match PAM formatting (ISO yyyy-mm-dd) if possible
            orbit_end = _norm(orbit_end)
            orbit_start = _norm(orbit_start)
            owner = promo.get('owner') or promo.get('Owner','')
            if owner:
                owners.add(owner)

            mismatch_type = ''
            mismatch_severity = ''
            if orbit_end and pam_end and orbit_end != pam_end:
                mismatch_type = 'End Date'
                mismatch_severity = 'warning'
            elif orbit_end and not pam_end:
                mismatch_type = 'Missing in PAM'
                mismatch_severity = 'error'
            elif pam_end and not orbit_end:
                mismatch_type = 'Missing in ORBIT'
                mismatch_severity = 'error'

            entries.append({
                'code': code,
                'orbit_id': orbit_id,
                'orbit_start_date': orbit_start,
                'orbit_end_date': orbit_end,
                'promo_start_date': pam_start,
                'promo_end_date': pam_end,
                'mismatch_type': mismatch_type,
                'mismatch_severity': mismatch_severity,
                'bill_facing_name': promo.get('bill_facing_name', ''),
                'owner': owner
            })

        # Date parsing / normalization helpers (standard output: MM/DD/YYYY)
        from datetime import datetime
        def _parse(d: str):
            if not d:
                return None
            s = str(d).strip()
            patterns = ['%Y-%m-%d','%m/%d/%Y','%m/%d/%y','%Y-%m-%d %H:%M:%S','%m/%d/%Y %H:%M:%S']
            for p in patterns:
                try:
                    return datetime.strptime(s, p).date()
                except Exception:
                    continue
            return None
        def _fmt(d: str):
            dt = _parse(d)
            return dt.strftime('%m/%d/%Y') if dt else (str(d).strip() if d else '')

        def sort_key(e: Dict[str, Any]):
            order = {'error': 0, 'warning': 1, '': 2}
            return (order.get(e.get('mismatch_severity',''),2), e.get('code',''))
        normalized_entries: List[Dict[str, Any]] = []
        for entry in entries:
            pam_end_raw = entry['promo_end_date']
            orbit_end_raw = entry['orbit_end_date']
            pam_start_raw = entry['promo_start_date']
            orbit_start_raw = entry['orbit_start_date']

            pam_end_fmt = _fmt(pam_end_raw)
            orbit_end_fmt = _fmt(orbit_end_raw)
            pam_start_fmt = _fmt(pam_start_raw)
            orbit_start_fmt = _fmt(orbit_start_raw)

            # Recalculate mismatch on parsed objects to avoid format-only differences
            pe_dt = _parse(pam_end_raw)
            oe_dt = _parse(orbit_end_raw)
            mismatch_type = entry['mismatch_type']
            mismatch_severity = entry['mismatch_severity']
            if pe_dt and oe_dt:
                if pe_dt != oe_dt:
                    mismatch_type = 'End Date'
                    mismatch_severity = 'warning'
                else:
                    mismatch_type = ''
                    mismatch_severity = ''
            elif oe_dt and not pe_dt:
                mismatch_type = 'Missing in PAM'
                mismatch_severity = 'error'
            elif pe_dt and not oe_dt:
                mismatch_type = 'Missing in ORBIT'
                mismatch_severity = 'error'

            entry.update({
                'orbit_end_date': orbit_end_fmt,
                'orbit_start_date': orbit_start_fmt,
                'promo_end_date': pam_end_fmt,
                'promo_start_date': pam_start_fmt,
                'mismatch_type': mismatch_type,
                'mismatch_severity': mismatch_severity
            })
            normalized_entries.append(entry)

        normalized_entries.sort(key=sort_key)

        return {'promos': normalized_entries, 'owners': sorted(owners)}

    # --- Date Mismatch Sync ---
    def sync_promo_end_date_from_orbit(self, promo_code: str, user_name: str = "System") -> Dict[str, Any]:
        """Synchronize promo_end_date in PAM table with the authoritative ORBIT value for a single promo.

        Returns dict: {success: bool, message: str, old_date: str, new_date: str}
        Records a version history entry with change_type 'Date Mismatch' when an update occurs.
        """
        try:
            before = self.db_manager.get_promo_by_code(promo_code) or {}
            if not before:
                return {'success': False, 'message': f'Promotion {promo_code} not found', 'old_date': None, 'new_date': None}
            orbit_id = before.get('orbit_id') or ''
            if not orbit_id:
                return {'success': False, 'message': f'Promotion {promo_code} missing orbit_id', 'old_date': before.get('promo_end_date'), 'new_date': None}
            orbit_rec = self.db_manager.get_orbit_record_by_orbit_id(str(orbit_id)) or {}
            orbit_end = orbit_rec.get('promo_end_date') or ''
            old_end = before.get('promo_end_date') or ''
            if not orbit_end:
                return {'success': False, 'message': f'No ORBIT end date available for {promo_code}', 'old_date': old_end, 'new_date': None}
            # Normalize display formatting (store raw orbit_end as-is to maintain DB fidelity)
            if orbit_end == old_end:
                return {'success': True, 'message': f'{promo_code} already synchronized', 'old_date': old_end, 'new_date': old_end}
            # Update PAM table
            updated = self.db_manager.update_promo_fields(promo_code, {'promo_end_date': orbit_end})
            if not updated:
                return {'success': False, 'message': f'Failed to update promo_end_date for {promo_code}', 'old_date': old_end, 'new_date': old_end}
            # Record version history diff under dedicated change_type 'Date Mismatch'
            diff = {'promo_end_date': {'old': old_end, 'new': orbit_end}}
            desc = f'Date mismatch sync: promo_end_date {old_end} -> {orbit_end}'
            # Recording system end date updates removed per history deletion
            return {'success': True, 'message': f'{promo_code} updated to ORBIT end date {orbit_end}', 'old_date': old_end, 'new_date': orbit_end}
        except Exception as e:
            return {'success': False, 'message': f'Unexpected error syncing {promo_code}: {e}', 'old_date': None, 'new_date': None}