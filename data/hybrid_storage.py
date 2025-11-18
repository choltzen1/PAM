"""
Enhanced PromoDataManager with Database Integration and Intelligent Caching
This hybrid approach provides maximum performance and data integrity for REGULAR PROMOTIONS ONLY.
Features:
- Smart cache invalidation (only refresh when DB changes)
- Background refresh (zero user-facing load time) 
- Manual refresh capability
- Optimized 30-minute cache TTL
- Performance monitoring
- Version history tracking

SPE promotions are excluded and will be handled by a separate system.
"""

import json
import os
import threading
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from threading import Lock, Timer
from data.database import DatabaseManager
from data.storage import PromoDataManager  # Import original for file management and utilities
from data.version_history import VersionHistoryManager

class HybridPromoDataManager:
    """
    Hybrid data manager for REGULAR PROMOTIONS ONLY that combines database-first approach 
    with intelligent caching for maximum performance and data integrity.
    
    SPE promotions are handled separately and not included in this manager.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.db_manager = DatabaseManager()
        
        # Initialize original data manager for file management and utility functions
        self._original_manager = PromoDataManager(data_dir)
        
        # Initialize version history manager
        self.version_history = VersionHistoryManager(data_dir)
        
        # Cache configuration - Optimized for promotion data patterns
        self._cache = {}
        self._cache_timestamp = None
        self._spe_cache = {}
        self._spe_cache_timestamp = None
        self._rebates_cache = {}
        self._rebates_cache_timestamp = None
        self._cache_ttl = timedelta(hours=2)  # 2-hour cache for stable promo data
        self._cache_lock = Lock()
        self._last_db_check = None
        self._background_timer = None
        
        # Performance tracking
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_db_loads = 0
        
        # Local storage for PAM-only fields
        self.workflow_file = os.path.join(data_dir, "workflow_data.json")
        self.uploads_dir = os.path.join(data_dir, "uploads")
        
        # Ensure directories exist
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(self.uploads_dir, exist_ok=True)
        
        self._initialize_workflow_storage()
        self._start_background_refresh()
    
    def _initialize_workflow_storage(self):
        """Initialize local storage for PAM-only workflow fields"""
        if not os.path.exists(self.workflow_file):
            with open(self.workflow_file, 'w') as f:
                json.dump({}, f)
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid using smart invalidation"""
        if not self._cache_timestamp:
            return False
        
        # Check TTL first (fast check)
        if datetime.now() - self._cache_timestamp >= self._cache_ttl:
            return False
        
        # Smart invalidation: check if database has newer data (slower check, done less frequently)
        if self._should_check_db_freshness():
            return not self._has_db_changed()
        
        return True
    
    def _should_check_db_freshness(self) -> bool:
        """Determine if we should check database for changes (throttled check)"""
        if not self._last_db_check:
            return True
        
        # Only check DB freshness every 5 minutes to avoid overhead
        return datetime.now() - self._last_db_check >= timedelta(minutes=5)
    
    def _has_db_changed(self) -> bool:
        """Check if database has been modified since last cache update"""
        try:
            self._last_db_check = datetime.now()
            
            # Get the most recent modification time from database
            # This is a lightweight query that just checks timestamps
            recent_promos = self.db_manager.get_recent_promos(days=1)  # Check last 24 hours
            
            if not recent_promos:
                return False
            
            # Check if any records are newer than our cache
            for promo in recent_promos:
                # Look for any timestamp fields that might indicate recent changes
                for date_field in ['promo_start_date', 'promo_end_date', 'updated_at', 'created_at']:
                    if date_field in promo and promo[date_field]:
                        try:
                            db_time = datetime.fromisoformat(str(promo[date_field]).replace('Z', '+00:00'))
                            if self._cache_timestamp and db_time > self._cache_timestamp:
                                return True
                        except (ValueError, TypeError):
                            continue
            
            return False
            
        except Exception as e:
            # If we can't check, assume no changes to avoid unnecessary refreshes
            print(f"Warning: Could not check database freshness: {e}")
            return False
    
    def _refresh_cache(self) -> Dict[str, Any]:
        """Refresh cache from database with performance tracking"""
        with self._cache_lock:
            if self._is_cache_valid():
                self._cache_hits += 1
                return self._cache
            
            self._cache_misses += 1
            self._total_db_loads += 1
            
            print(f"Refreshing promotion cache... (Load #{self._total_db_loads})")
            start_time = time.time()
            
            # Get fresh data from database
            db_records = self.db_manager.get_all_promos()
            
            # Load local workflow data
            workflow_data = self._load_workflow_data()
            
            # Merge database and workflow data
            merged_data = {}
            for record in db_records:
                code = str(record.get('code', ''))
                if code:
                    # Convert DB record to PAM format (handle type conversion)
                    record_dict = {str(k): v for k, v in record.items()}  # Ensure string keys
                    promo_data = self.db_manager.convert_db_record_to_json_format(record_dict)
                    
                    # Merge with local workflow data if exists
                    if code in workflow_data:
                        promo_data.update(workflow_data[code])
                    
                    merged_data[code] = promo_data

            # Overlay any JSON-only promos (e.g., newly ingested before DB replication)
            try:
                json_promos = self._original_manager._load_json(self._original_manager.promo_file)  # type: ignore[attr-defined]
                for jcode, jdata in json_promos.items():
                    if not jcode:
                        continue
                    if jcode in merged_data:
                        # Update DB record with any JSON overrides (recent edits)
                        merged = merged_data[jcode]
                        merged.update(jdata)
                        # Also merge workflow fields if present
                        if jcode in workflow_data:
                            merged.update(workflow_data[jcode])
                    else:
                        # Pure JSON-only promo (add and merge workflow if exists)
                        new_entry = dict(jdata)
                        if jcode in workflow_data:
                            new_entry.update(workflow_data[jcode])
                        merged_data[jcode] = new_entry
            except Exception as e:
                print(f"Warning: failed overlaying JSON promos into hybrid cache: {e}")
            
            # Update cache
            self._cache = merged_data
            self._cache_timestamp = datetime.now()
            
            load_time = time.time() - start_time
            print(f"Cache refreshed: {len(merged_data)} promotions loaded in {load_time:.2f}s")
            
            return self._cache
    
    def _refresh_spe_cache(self) -> Dict[str, Any]:
        """Refresh SPE cache from database"""
        with self._cache_lock:
            if self._spe_cache_timestamp and datetime.now() - self._spe_cache_timestamp < self._cache_ttl:
                return self._spe_cache
            
            # Get fresh SPE data from database
            start_time = time.time()
            db_records = self.db_manager.get_all_spe_promos()
            
            # Load local workflow data
            workflow_data = self._load_workflow_data()
            
            # Merge database and workflow data
            merged_data = {}
            for record in db_records:
                code = str(record.get('code', ''))
                if code:
                    # Convert DB record to PAM format
                    record_dict = {str(k): v for k, v in record.items()}
                    promo_data = self.db_manager.convert_db_record_to_json_format(record_dict)
                    
                    # Merge with local workflow data if exists
                    if code in workflow_data:
                        promo_data.update(workflow_data[code])
                    
                    merged_data[code] = promo_data
            
            # Update SPE cache
            self._spe_cache = merged_data
            self._spe_cache_timestamp = datetime.now()
            
            load_time = time.time() - start_time
            print(f"SPE cache refreshed: {len(merged_data)} SPE promotions loaded in {load_time:.2f}s")
            
            return self._spe_cache
    
    def _refresh_rebates_cache(self) -> Dict[str, Any]:
        """Refresh Rebates cache from database"""
        with self._cache_lock:
            if self._rebates_cache_timestamp and datetime.now() - self._rebates_cache_timestamp < self._cache_ttl:
                return self._rebates_cache
            
            # Get fresh Rebates data from database
            start_time = time.time()
            db_records = self.db_manager.get_all_rebates()
            
            # Load local workflow data
            workflow_data = self._load_workflow_data()
            
            # Merge database and workflow data
            merged_data = {}
            for i, record in enumerate(db_records):
                # Use simple index-based key - no filtering, no code generation
                key = f"rebate_{i}"
                
                # Convert DB record to PAM format
                record_dict = {str(k): v for k, v in record.items()}
                promo_data = self.db_manager.convert_db_record_to_json_format(record_dict)
                
                # Store the index key for template access
                promo_data['key'] = key
                
                # Merge with local workflow data if exists
                if key in workflow_data:
                    promo_data.update(workflow_data[key])
                
                merged_data[key] = promo_data
            
            # Update Rebates cache
            self._rebates_cache = merged_data
            self._rebates_cache_timestamp = datetime.now()
            
            load_time = time.time() - start_time
            print(f"Rebates cache refreshed: {len(merged_data)} rebates loaded in {load_time:.2f}s")
            
            return self._rebates_cache
    
    def _load_workflow_data(self) -> Dict[str, Any]:
        """Load PAM-only workflow data from local storage and promotions.json"""
        workflow_data = {}
        
        # Load from workflow_data.json
        try:
            with open(self.workflow_file, 'r') as f:
                workflow_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            workflow_data = {}
        
        # Also load from promotions.json for promo_notes and other fields
        try:
            promo_file = os.path.join(self.data_dir, "promotions.json")
            with open(promo_file, 'r') as f:
                promo_json_data = json.load(f)
                
                # Merge promo_notes and other PAM-specific fields
                for code, promo_data in promo_json_data.items():
                    if code not in workflow_data:
                        workflow_data[code] = {}
                    
                    # Copy PAM-specific fields from promotions.json
                    pam_fields = ['promo_notes', 'spe_notes', 'notes', 'generated_sql', 'sql_generated_at', 
                                 'sql_generation_time', 'sql_length', 'uploaded_files', 'version_history',
                                 'last_changes', 'created_at', 'updated_at', 'test_status', 'zlab_status']
                    
                    for field in pam_fields:
                        if field in promo_data:
                            workflow_data[code][field] = promo_data[field]
                            
        except (FileNotFoundError, json.JSONDecodeError):
            pass
            
        return workflow_data
    
    def _save_workflow_data(self, workflow_data: Dict[str, Any]):
        """Save PAM-only workflow data to local storage"""
        with open(self.workflow_file, 'w') as f:
            json.dump(workflow_data, f, indent=2)
    
    # OPTIMIZATION METHODS
    
    def _start_background_refresh(self):
        """Start background cache refresh timer"""
        if self._background_timer:
            self._background_timer.cancel()
        
        # Refresh cache every 25 minutes in background (before 30-min TTL expires)
        self._background_timer = Timer(25 * 60, self._background_refresh_worker)
        self._background_timer.daemon = True
        self._background_timer.start()
        print("Background cache refresh started (every 25 minutes)")
    
    def _background_refresh_worker(self):
        """Worker function for background cache refresh"""
        try:
            print("Background refresh: Checking for database updates...")
            
            # Force a cache check (but don't load if not needed)
            if self._has_db_changed():
                print("Background refresh: Database changes detected, refreshing cache...")
                self.force_refresh()
            else:
                print("Background refresh: No database changes, keeping current cache")
                
        except Exception as e:
            print(f"Background refresh error: {e}")
        finally:
            # Schedule next background refresh
            self._start_background_refresh()
    
    def stop_background_refresh(self):
        """Stop background refresh timer (useful for cleanup)"""
        if self._background_timer:
            self._background_timer.cancel()
            self._background_timer = None
            print("Background cache refresh stopped")
    
    # PUBLIC API - Drop-in replacement for existing PromoDataManager
    
    def get_all_promos(self) -> Dict[str, Any]:
        """Get all promotions (cached for performance)"""
        return self._refresh_cache()
    
    def get_promo(self, promo_code: str) -> Dict[str, Any]:
        """Get a specific promotion - check JSON first (for edits), then database"""
        # First check JSON file for any edits
        json_promo = self._original_manager.get_promo(promo_code)
        if json_promo:
            # If we have JSON data, use it (this contains any edits)
            return json_promo
        
        # Fall back to database if not in JSON
        all_promos = self.get_all_promos()
        return all_promos.get(promo_code, {})
    
    def get_all_spe_promos(self) -> Dict[str, Any]:
        """Get all SPE promotions from database (cached for performance)"""
        return self._refresh_spe_cache()
    
    def get_all_rebates(self) -> Dict[str, Any]:
        """Get all rebate promotions from database (cached for performance)"""
        return self._refresh_rebates_cache()
    
    def get_spe_promo(self, promo_code: str) -> Dict[str, Any]:
        """Get a specific SPE promotion"""
        all_spe = self.get_all_spe_promos()
        return all_spe.get(promo_code, {})
    
    def get_rebate(self, rebate_code: str) -> Dict[str, Any]:
        """Get a specific rebate"""
        all_rebates = self.get_all_rebates()
        return all_rebates.get(rebate_code, {})
    
    def get_rebate_owners(self) -> List[str]:
        """Get unique owners from all rebates for filter dropdown"""
        all_rebates = self.get_all_rebates()
        owners = sorted(set(rebate.get('owner', '') for rebate in all_rebates.values() if rebate.get('owner')))
        return owners
    
    def get_date_mismatched_promos(self) -> Dict[str, Any]:
        """Get promotions with date mismatches between ORBIT (authoritative DB) and PAM (local JSON/db overlay).

        Uses EXACT same data retrieval as RDC page (get_paginated_execution_type).
        """
        owners: set[str] = set()
        entries: list[Dict[str, Any]] = []

        # Use EXACT same method as RDC page - get ALL RDC records with owner field populated
        paginated_data = self.db_manager.get_paginated_execution_type(
            execution_type="RDC",
            page=1,
            per_page=10000,  # Get all records
            search="",
            owner_filter="all",
            upcoming_only_when_no_query=False,
            force_upcoming=False
        )
        
        db_records = paginated_data['promotions']
        
        # DEBUG: Log what we actually got from paginated query
        import logging
        logger = logging.getLogger(__name__)
        if db_records:
            logger.info(f"PAGINATED returned {len(db_records)} records")
            first_with_owner = next((r for r in db_records if r.get('owner')), None)
            if first_with_owner:
                logger.info(f"PAGINATED first with owner: '{first_with_owner.get('owner')}' code={first_with_owner.get('code')}")
            else:
                logger.info("PAGINATED NO RECORDS WITH OWNER FOUND!")
        
        orbit_by_code: Dict[str, Dict[str, Any]] = {}
        for rec in db_records:
            code = str(rec.get('code','') or '')
            if not code:
                continue
            orbit_by_code[code] = rec

        # Load legacy PAM JSON edits (if file exists)
        pam_json: Dict[str, Any] = {}
        try:
            with open(os.path.join(self.data_dir, 'promotions.json'),'r') as f:
                pam_json = json.load(f)
        except Exception:
            pam_json = {}

        # Combine code universe
        all_codes = set(orbit_by_code.keys()) | set(pam_json.keys())

        # Build mismatch records
        import logging
        logger = logging.getLogger(__name__)
        first_logged = False
        for code in all_codes:
            ob = orbit_by_code.get(code, {})
            pj = pam_json.get(code, {})
            if not first_logged and ob:
                logger.info(f"MISMATCH DEBUG first ob keys: {list(ob.keys())}")
                logger.info(f"MISMATCH DEBUG first ob owner: '{ob.get('owner')}'")
                first_logged = True
            orbit_end = ob.get('promo_end_date','')
            orbit_start = ob.get('promo_start_date','')
            pam_end = pj.get('promo_end_date','') or ob.get('promo_end_date','')
            pam_start = pj.get('promo_start_date','') or ob.get('promo_start_date','')
            owner = ob.get('owner', '')
            bill_facing_name = ob.get('bill_facing_name') or pj.get('bill_facing_name','')
            orbit_id = ob.get('orbit_id') or pj.get('orbit_id','')

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
                'bill_facing_name': bill_facing_name,
                'owner': owner
            })

        def sort_key(e: Dict[str, Any]):
            order = {'error': 0, 'warning': 1, '': 2}
            return (order.get(e.get('mismatch_severity',''),2), e.get('code',''))
        entries.sort(key=sort_key)

        return {'promos': entries, 'owners': sorted(paginated_data['owners'])}
    
    def get_paginated_promos(self, page: int = 1, per_page: int = 25, 
                           search: str = "", owner_filter: str = "all") -> Dict[str, Any]:
        """Get paginated promotions with filtering (optimized in-memory)"""
        all_promos = self.get_all_promos()
        promo_list = list(all_promos.values())
        
        # Apply filters
        if search:
            search_lower = search.lower()
            promo_list = [
                promo for promo in promo_list 
                if (search_lower in promo.get('code', '').lower() or 
                    search_lower in promo.get('owner', '').lower() or
                    search_lower in promo.get('bill_facing_name', '').lower())
            ]
        
        if owner_filter and owner_filter != "all":
            promo_list = [promo for promo in promo_list if promo.get('owner', '') == owner_filter]
        
        # Sort by updated_at (most recent first) or code if no updated_at
        promo_list.sort(key=lambda x: x.get('updated_at', x.get('code', '')), reverse=True)
        
        # Calculate pagination
        total_items = len(promo_list)
        total_pages = (total_items + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        
        paginated_promos = promo_list[start:end]
        
        # Get unique owners for filter dropdown
        all_owners = sorted(set(promo.get('owner', '') for promo in all_promos.values() if promo.get('owner')))
        
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

    def get_pam_only_paginated_promos(self, page: int = 1, per_page: int = 25,
                                      search: str = "", owner_filter: str = "all") -> Dict[str, Any]:
        """Return ONLY promotions that exist in PAM JSON (exclude raw Orbit DB-only records)."""
        try:
            json_promos = self._original_manager._load_json(self._original_manager.promo_file)  # type: ignore[attr-defined]
        except Exception:
            json_promos = {}
        # Build list ensuring code present inside each record
        promo_list = []
        for code, pdata in json_promos.items():
            if not code:
                continue
            if 'code' not in pdata:
                pdata = dict(pdata)
                pdata['code'] = code
            promo_list.append(pdata)

        # Apply filters
        if search:
            s = search.lower()
            promo_list = [p for p in promo_list if (
                s in p.get('code','').lower() or
                s in p.get('owner','').lower() or
                s in p.get('bill_facing_name','').lower()
            )]
        if owner_filter and owner_filter != 'all':
            promo_list = [p for p in promo_list if p.get('owner','') == owner_filter]

        promo_list.sort(key=lambda x: x.get('updated_at', x.get('code','')), reverse=True)

        total_items = len(promo_list)
        total_pages = (total_items + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        paginated = promo_list[start:end]

        owners = sorted(set(p.get('owner','') for p in promo_list if p.get('owner')))
        return {
            'promotions': paginated,
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
            'owners': owners
        }
    
    def save_promo(self, promo_code: str, promo_data: Dict[str, Any], user_name: str = "System"):
        """Save promotion data with version history tracking"""
        # Get existing data for comparison
        existing_data = self.get_promo(promo_code)
        is_new_promo = existing_data is None
        
        # TEMPORARY SOLUTION: Until PAM database is implemented,
        # save everything to JSON file to maintain current functionality
        
        # Use the original manager's save method to maintain current workflow
        self._original_manager.save_promo(promo_code, promo_data, user_name)
        
        # Track version history
        if is_new_promo:
            # Record creation
            self.version_history.record_promo_creation(promo_code, user_name, promo_data)
        else:
            # Compare data and record changes
            changed_fields = {}
            for key, new_value in promo_data.items():
                # Skip non-meaningful timestamp/system-only fields from version history diffs
                if key in {"updated_at", "created_at", "last_sync"}:
                    continue
                old_value = existing_data.get(key)
                if old_value != new_value:
                    changed_fields[key] = {
                        'old': old_value,
                        'new': new_value
                    }
            
            if changed_fields:
                self.version_history.record_promo_modification(promo_code, user_name, changed_fields)
        
        # Invalidate cache to force refresh
        self._cache_timestamp = None
        
        # Also update our workflow data cache
        workflow_data = self._load_workflow_data()
        if promo_code not in workflow_data:
            workflow_data[promo_code] = {}
        
        # Extract workflow-specific fields for our cache
        workflow_fields = self._extract_workflow_fields(promo_data)
        workflow_data[promo_code].update(workflow_fields)
        workflow_data[promo_code]['updated_at'] = datetime.now().isoformat()
        workflow_data[promo_code]['updated_by'] = user_name
        
        self._save_workflow_data(workflow_data)
    
    def record_sql_generation(self, promo_code: str, user_name: str, generation_time: float, sql_length: int):
        """Record SQL generation in version history"""
        self.version_history.record_sql_generation(promo_code, user_name, generation_time, sql_length)

    def record_date_mismatch_sql(self, promo_code: str, user_name: str, generation_time: float, sql_length: int):
        """Record date mismatch SQL generation in version history"""
        if hasattr(self.version_history, 'record_date_mismatch_sql'):
            self.version_history.record_date_mismatch_sql(promo_code, user_name, generation_time, sql_length)
    
    def record_file_upload(self, promo_code: str, user_name: str, file_type: str, filename: str):
        """Record file upload in version history"""
        self.version_history.record_file_upload(promo_code, user_name, file_type, filename)
    
    def get_promo_version_history(self, promo_code: str) -> List[Dict[str, Any]]:
        """Get version history for a specific promotion"""
        return self.version_history.get_promo_history(promo_code)
    
    def get_all_promotions_with_history(self) -> List[Dict[str, Any]]:
        """Get all promotions with version history for the version history page"""
        # Get promotions with history from version history DB
        history_data = self.version_history.get_all_promotions_with_history()
        
        # Get current promotion data
        current_promos = self.get_all_promos()
        
        # Combine the data
        promotions_with_history = []
        for history_item in history_data:
            promo_code = history_item['promo_code']
            
            # Find current promo data
            current_promo = current_promos.get(promo_code)
            if current_promo:
                # Get detailed change history
                # Use curated changes if available
                if hasattr(self.version_history, 'get_curated_promo_changes'):
                    changes = self.version_history.get_curated_promo_changes(promo_code)
                else:
                    changes = self.get_promo_version_history(promo_code)
                
                promo_with_history = {
                    'promo_code': promo_code,
                    'orbit_id': current_promo.get('orbit_id', ''),
                    'status': current_promo.get('status', 'Active'),
                    'bill_facing_name': current_promo.get('bill_facing_name', ''),
                    'start_date': current_promo.get('promo_start_date', current_promo.get('promo_start_date', '')),
                    'end_date': current_promo.get('promo_end_date', ''),
                    'promo_owner': current_promo.get('owner', current_promo.get('Owner', '')),
                    'changes': changes
                }
                promotions_with_history.append(promo_with_history)
        
        return promotions_with_history
    
    def _extract_db_fields(self, promo_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract fields that belong in the database"""
        db_field_names = [
            'code', 'description', 'owner', 'bill_facing_name', 'orbit_id',
            'promo_notes', 'discount', 'amount', 'nseip_drop', 'dcd_web_cart',
            'product_type', 'bogo', 'fpd_display_promo', 'on_menu', 'market_group',
            'store_group', 'promo_start_date', 'promo_end_date', 'comm_end_date',
            'promo_duration', 'delay_time', 'application_grace_period',
            'device_sales_type', 'activation_type', 'active_line_required',
            'maintain_soc', 'crffc_maintainactivelinedev', 'limit_per_ban',
            'soc_grouping', 'account_type', 'sales_application', 'operator_id',
            'sku_group_id', 'device_status_group_id', 'clawback_indicator',
            'Broken_Trade', 'Anticipated_volume_take_rates_total', 'Desired_Execution'
        ]
        
        return {key: promo_data.get(key) for key in db_field_names if key in promo_data}
    
    def _extract_workflow_fields(self, promo_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract fields that are PAM workflow-only"""
        workflow_field_names = [
            'sku_link', 'tradein_link', 'version_history', 'uploaded_files',
            'generated_sql', 'sql_file', 'last_changes', 'jira_ticket',
            'initiative_name', 'segment_name', 'sub_segment', 'segment_group_id',
            'segment_level'
        ]
        
        return {key: promo_data.get(key) for key in workflow_field_names if key in promo_data}
    
    def force_refresh(self) -> Dict[str, Any]:
        """Force immediate cache refresh (enhanced manual refresh capability)"""
        print("Manual cache refresh requested...")
        self._cache_timestamp = None  # Invalidate cache
        result = self._refresh_cache()
        print("Manual cache refresh completed")
        return result

    def full_data_refresh(self) -> Dict[str, Any]:
        """Perform a full data refresh of all caches (promos, SPE, rebates).
        Returns counts and timing info for each segment."""
        with self._cache_lock:
            print("Full data refresh requested...")
            overall_start = time.time()

            # Invalidate all timestamps so subsequent refresh calls reload
            self._cache_timestamp = None
            self._spe_cache_timestamp = None
            self._rebates_cache_timestamp = None

            # Refresh each cache capturing timing
            stats: Dict[str, Any] = {}
            start = time.time()
            promos = self._refresh_cache()
            stats['promotions_loaded'] = len(promos)
            stats['promotions_time'] = round(time.time() - start, 3)

            start = time.time()
            spe = self._refresh_spe_cache()
            stats['spe_loaded'] = len(spe)
            stats['spe_time'] = round(time.time() - start, 3)

            start = time.time()
            rebates = self._refresh_rebates_cache()
            stats['rebates_loaded'] = len(rebates)
            stats['rebates_time'] = round(time.time() - start, 3)

            stats['total_time'] = round(time.time() - overall_start, 3)
            print(f"Full data refresh completed in {stats['total_time']}s")
            return stats
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get enhanced cache status for debugging and monitoring"""
        cache_age = None
        if self._cache_timestamp:
            cache_age = (datetime.now() - self._cache_timestamp).total_seconds()
        
        return {
            'cached_items': len(self._cache),
            'cache_age_seconds': cache_age,
            'cache_age_minutes': cache_age / 60 if cache_age else None,
            'cache_valid': self._is_cache_valid(),
            'cache_ttl_minutes': self._cache_ttl.total_seconds() / 60,
            'last_refresh': self._cache_timestamp.isoformat() if self._cache_timestamp else None,
            'last_db_check': self._last_db_check.isoformat() if self._last_db_check else None,
            'total_cache_hits': self._cache_hits,
            'total_cache_misses': self._cache_misses,
            'total_db_loads': self._total_db_loads,
            'cache_hit_ratio': f"{(self._cache_hits / (self._cache_hits + self._cache_misses) * 100):.1f}%" if (self._cache_hits + self._cache_misses) > 0 else "N/A",
            'background_refresh_active': self._background_timer is not None and self._background_timer.is_alive()
        }
    
    # ===== FILE MANAGEMENT METHODS (Delegated to Original Manager) =====
    
    def save_excel_file(self, promo_code: str, file, file_type: str):
        """Save Excel file for promotion (delegated to original manager)"""
        return self._original_manager.save_excel_file(promo_code, file, file_type)
    
    def save_sql_file(self, promo_code: str, sql_content: str, filename: str) -> str:
        """Save SQL file for promotion (delegated to original manager)"""
        return self._original_manager.save_sql_file(promo_code, sql_content, filename)
    
    def get_uploaded_file_info(self, promo_code: str, file_type: str):
        """Get uploaded file info (delegated to original manager)"""
        return self._original_manager.get_uploaded_file_info(promo_code, file_type)
    
    def delete_uploaded_file(self, promo_code: str, file_type: str) -> bool:
        """Delete uploaded file (delegated to original manager)"""
        return self._original_manager.delete_uploaded_file(promo_code, file_type)
    
    def get_file_path(self, promo_code: str, file_type: str):
        """Get file path (delegated to original manager)"""
        return self._original_manager.get_file_path(promo_code, file_type)
    
    # ===== VERSION HISTORY METHODS (Delegated to Original Manager) =====
    
    def add_permanent_version_entry(self, promo_code: str, entry: str, is_spe: bool = False):
        """Add permanent version entry (delegated to original manager)"""
        return self._original_manager.add_permanent_version_entry(promo_code, entry, is_spe)
    
    def add_approval_version(self, promo_code: str, version_number: int, approver: str, is_spe: bool = False):
        """Add approval version (delegated to original manager)"""
        return self._original_manager.add_approval_version(promo_code, version_number, approver, is_spe)
    
    def add_pcr_version(self, promo_code: str, version_number: int, user_name: str, is_spe: bool = False):
        """Add PCR version (delegated to original manager)"""
        return self._original_manager.add_pcr_version(promo_code, version_number, user_name, is_spe)
    
    def delete_promo(self, promo_code: str):
        """Delete promotion from DB + local artifacts and invalidate cache.

        Invokes underlying DatabaseManager.delete_promo (hard delete) if available.
        Falls back to original manager (no-op) otherwise.
        """
        # Remove from cache memory
        if promo_code in self._cache:
            del self._cache[promo_code]

        # Remove from workflow auxiliary file
        workflow_data = self._load_workflow_data()
        if promo_code in workflow_data:
            del workflow_data[promo_code]
            self._save_workflow_data(workflow_data)

        # Attempt DB hard delete
        deleted = False
        if hasattr(self.db_manager, 'delete_promo'):
            try:
                deleted = self.db_manager.delete_promo(promo_code)
            except Exception:
                deleted = False
        else:
            # Fallback to original manager if it implemented something
            try:
                self._original_manager.delete_promo(promo_code)
            except Exception:
                pass

        # Invalidate cache timestamp so next access reloads
        self._cache_timestamp = None
        return deleted
    
    def get_promo_list(self):
        """Get promotion list (optimized to use cache)"""
        all_promos = self.get_all_promos()
        return [promo for promo in all_promos.values()]
    
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
        """Return the full SOC grouping details as formatted text."""
        import os
        soc_file_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'soc_grouping.txt')
        details = []
        
        try:
            with open(soc_file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if line and '|' in line:
                        # Split on the first | to separate group info from details
                        group_part, details_part = line.split('|', 1)
                        
                        # Format the group part
                        details.append(f"<strong>{group_part.strip()}</strong>")
                        
                        # Format the details part if it exists
                        if details_part.strip():
                            # Split details by comma and format as bullet points
                            detail_items = [item.strip() for item in details_part.split(',') if item.strip()]
                            for item in detail_items:
                                details.append(f"• {item}")
                        
                        details.append("")  # Add blank line between groups
                    elif line:
                        # Handle lines without | separator
                        details.append(f"<strong>{line}</strong>")
                        details.append("")
            
            return "<br>".join(details)
        
        except FileNotFoundError:
            return "SOC Grouping file not found."
        except Exception as e:
            return f"Error reading SOC groupings: {str(e)}"
    
    def get_account_types(self) -> list:
        """Get list of account type codes from account_types.txt"""
        return [
            "A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10",
            "A11", "A12", "A13", "A14", "A15", "A16", "A17", "ALL", "AT1", "AT2",
            "AT3", "AT4", "AT5", "AT6", "AT7", "GST"
        ]
    
    def get_account_type_details(self) -> str:
        """Get detailed account type information from account_types.txt"""
        import os
        try:
            account_types_file = os.path.join(os.path.dirname(__file__), '..', 'static', 'account_types.txt')
            
            with open(account_types_file, 'r', encoding='utf-8') as file:
                content = file.read().strip()
            
            if not content:
                return "No account type information found."
            
            details = []
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        account_type = parts[0].strip()
                        description = parts[1].strip()
                        
                        details.append(f"<strong>{account_type}</strong>")
                        if description:
                            details.append(description)
                        details.append("")
                else:
                    if line:
                        # Handle lines without | separator
                        details.append(f"<strong>{line}</strong>")
                        details.append("")
            
            return "<br>".join(details)
        
        except FileNotFoundError:
            return "Account Types file not found."
        except Exception as e:
            return f"Error reading account types: {str(e)}"
    
    def get_sales_applications(self) -> list:
        """Get list of sales application codes from sales_apps.txt"""
        import os
        try:
            sales_apps_file = os.path.join(os.path.dirname(__file__), '..', 'static', 'sales_apps.txt')
            
            with open(sales_apps_file, 'r', encoding='utf-8') as file:
                content = file.read().strip()
            
            if not content:
                return []
            
            codes = []
            for raw in content.split('\n'):
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('|')
                if not parts:
                    continue
                code = parts[0].strip()
                if code:
                    codes.append(code)
            return codes
        except FileNotFoundError:
            print(f"Warning: sales_apps.txt file not found.")
            return []
        except Exception as e:
            print(f"Error reading sales applications: {e}")
            return []
    
    def get_sales_application_details(self) -> str:
        """Get detailed sales application information from sales_apps.txt"""
        import os
        try:
            sales_apps_file = os.path.join(os.path.dirname(__file__), '..', 'static', 'sales_apps.txt')
            
            with open(sales_apps_file, 'r', encoding='utf-8') as file:
                content = file.read().strip()
            
            if not content:
                return "No sales application information found."
            out_blocks = []
            for raw in content.split('\n'):
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('|')
                if len(parts) < 1:
                    continue
                code = parts[0].strip()
                label = parts[1].strip() if len(parts) > 1 else ''
                items_part = parts[2].strip() if len(parts) > 2 else ''
                block_parts = ["<div class='grouping-row'>"]
                if label:
                    block_parts.append(f"<div class='grouping-head'><strong>{code}</strong> - {label}</div>")
                else:
                    block_parts.append(f"<div class='grouping-head'><strong>{code}</strong></div>")
                if items_part:
                    items = [i.strip() for i in items_part.split(',') if i.strip()]
                    if items:
                        block_parts.append("<ul class='grouping-items'>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
                block_parts.append("</div>")
                out_blocks.append("".join(block_parts))
            return "".join(out_blocks) or "No sales application information found."
        
        except FileNotFoundError:
            return "Sales Applications file not found."
        except Exception as e:
            return f"Error reading sales applications: {str(e)}"
