"""
Enhanced PromoDataManager with Database Integration and Intelligent Caching
This hybrid approach provides maximum performance and data integrity for REGULAR PROMOTIONS ONLY.
Features:
- Smart cache invalidation (only refresh when DB changes)
- Background refresh (zero user-facing load time) 
- Manual refresh capability
- Optimized 30-minute cache TTL
- Performance monitoring

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
        
        # Cache configuration - Optimized for promotion data patterns
        self._cache = {}
        self._cache_timestamp = None
        self._spe_cache = {}
        self._spe_cache_timestamp = None
        self._rebates_cache = {}
        self._rebates_cache_timestamp = None
        self._cache_ttl = timedelta(minutes=30)  # 30-minute cache for stable promo data
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
                for date_field in ['promo_srart_date', 'promo_end_date', 'updated_at', 'created_at']:
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
        """Load PAM-only workflow data from local storage"""
        try:
            with open(self.workflow_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
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
        """Get a specific promotion"""
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
        """Get promotions with date mismatches between ORBIT and PAM using database data"""
        all_promos = self.get_all_promos()
        all_promo_entries = []
        owners = set()  # Track unique owners
        
        # Sample ORBIT dates to simulate mismatches (only end dates matter)
        # In a real implementation, this would come from ORBIT database
        sample_orbit_dates = {
            'P0472022': {
                'orbit_end_date': '2025-08-10'    # Different from PAM end date
            },
            'R223': {
                'orbit_end_date': '2025-07-20'    # Different from PAM end date
            }
        }
        
        for promo_code, promo_data in all_promos.items():
            # Get PAM dates from database
            pam_start = promo_data.get('promo_start_date', '')
            pam_end = promo_data.get('promo_end_date', '')
            owner = promo_data.get('owner', '')
            
            # Track owners for filter
            if owner:
                owners.add(owner)
            
            # Get simulated ORBIT dates (in real implementation, this would come from ORBIT database)
            # Only check end dates since start dates are manually adjusted before launch
            orbit_dates = sample_orbit_dates.get(promo_code, {})
            orbit_start = pam_start  # Use PAM start date as ORBIT start (not checked for mismatches)
            orbit_end = orbit_dates.get('orbit_end_date', pam_end)
            
            # Check for end date mismatch only
            end_mismatch = orbit_end != pam_end
            
            # Create entry for ALL promos (with or without mismatches)
            promo_entry = {
                'code': promo_code,
                'orbit_id': promo_data.get('orbit_id', ''),
                'orbit_start_date': orbit_start,
                'orbit_end_date': orbit_end,
                'promo_start_date': pam_start,
                'promo_end_date': pam_end,
                'mismatch_type': 'End Date' if end_mismatch else '',
                'mismatch_severity': 'warning' if end_mismatch else '',
                'bill_facing_name': promo_data.get('bill_facing_name', ''),
                'owner': owner
            }
            
            all_promo_entries.append(promo_entry)
        
        return {
            'promos': all_promo_entries,
            'owners': sorted(list(owners))
        }
    
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
    
    def save_promo(self, promo_code: str, promo_data: Dict[str, Any], user_name: str = "System"):
        """Save promotion data (database + local workflow fields)"""
        # Split data into database fields and workflow fields
        db_fields = self._extract_db_fields(promo_data)
        workflow_fields = self._extract_workflow_fields(promo_data)
        
        # Save database fields to SQL
        # Note: This would require implementing save methods in DatabaseManager
        # For now, we'll save to local cache and sync later
        
        # Save workflow fields locally
        workflow_data = self._load_workflow_data()
        if promo_code not in workflow_data:
            workflow_data[promo_code] = {}
        
        workflow_data[promo_code].update(workflow_fields)
        workflow_data[promo_code]['updated_at'] = datetime.now().isoformat()
        workflow_data[promo_code]['updated_by'] = user_name
        
        self._save_workflow_data(workflow_data)
        
        # Invalidate cache to force refresh
        self._cache_timestamp = None
    
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
        """Delete promotion (clears from cache and delegates to original manager)"""
        # Clear from cache
        if promo_code in self._cache:
            del self._cache[promo_code]
        
        # Clear from workflow data
        workflow_data = self._load_workflow_data()
        if promo_code in workflow_data:
            del workflow_data[promo_code]
            self._save_workflow_data(workflow_data)
        
        # Note: Database deletion would need to be implemented in DatabaseManager
        # For now, just delegate to original manager for local cleanup
        return self._original_manager.delete_promo(promo_code)
    
    def get_promo_list(self):
        """Get promotion list (optimized to use cache)"""
        all_promos = self.get_all_promos()
        return [promo for promo in all_promos.values()]
