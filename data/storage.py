import json
import os
import shutil
from typing import Dict, Any, List, Optional
from datetime import datetime
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from .database import DatabaseManager


class PromoDataManager:
    """Manages persistent storage for promotion data using live database connection"""
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.uploads_dir = os.path.join(data_dir, "uploads")
        self.promo_uploads_dir = os.path.join(self.uploads_dir, "promotions")
        # File paths for JSON storage (SPE/rebates legacy). RDC promos now DB-only.
        self.promo_file = os.path.join(data_dir, "promotions.json")
        self.spe_file = os.path.join(data_dir, "spe_promotions.json")
        self.rebates_file = os.path.join(data_dir, "rebates.json")
        # Auto-archive legacy JSON files (one-time rename to .bak) while keeping attributes pointing to new names
        self._auto_archive_json_files()
        # Initialize database manager for live data
        self.db_manager = DatabaseManager()
        # Ensure upload directories exist
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(self.uploads_dir, exist_ok=True)
        os.makedirs(self.promo_uploads_dir, exist_ok=True)

    def _auto_archive_json_files(self):
        mapping = {
            'promo_file': 'promotions.json',
            'spe_file': 'spe_promotions.json',
            'rebates_file': 'rebates.json'
        }
        for attr, fname in mapping.items():
            orig_path = getattr(self, attr)
            bak_path = orig_path + '.bak'
            try:
                if os.path.exists(orig_path) and not os.path.exists(bak_path):
                    os.rename(orig_path, bak_path)
                if os.path.exists(bak_path):
                    setattr(self, attr, bak_path)
            except Exception:
                # Non-fatal; leave paths as-is
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
                return self.db_manager.convert_db_record_to_json_format(db_record)
            return {}
        except Exception as e:
            print(f"Database lookup failed for {promo_code}: {e}")
            return {}
    
    def get_spe_promo(self, promo_code: str) -> Dict[str, Any]:
        """Get a specific SPE promotion by code (DB)."""
        try:
            for r in self.db_manager.get_promos_by_execution_type("SPE"):
                if str(r.get('code','')).upper() == promo_code.upper():
                    return self.db_manager.convert_db_record_to_json_format({str(k): v for k,v in r.items()})
        except Exception:
            pass
        return {}
    
    def get_all_promos(self) -> Dict[str, Any]:
        """Get all promotions (RDC) from database (no JSON overlay)."""
        try:
            db_records = self.db_manager.get_promos_by_execution_type("RDC")
        except Exception as e:
            print(f"Database lookup failed for all promos: {e}")
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
        try:
            db_records = self.db_manager.get_promos_by_execution_type("RDC")
        except Exception as e:
            print(f"Database lookup failed for paginated promos: {e}")
            db_records = []
        promo_list: List[Dict[str, Any]] = []
        for record in db_records:
            record_dict: Dict[str, Any] = {str(k): v for k, v in record.items()} if record else {}
            promo_list.append(self.db_manager.convert_db_record_to_json_format(record_dict))
        
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
    
    def get_all_spe_promos(self) -> Dict[str, Any]:
        """Get all SPE promotions (DB)."""
        out: Dict[str, Any] = {}
        try:
            for r in self.db_manager.get_promos_by_execution_type("SPE"):
                conv = self.db_manager.convert_db_record_to_json_format({str(k): v for k,v in r.items()})
                c = conv.get('code')
                if c:
                    out[c] = conv
        except Exception:
            pass
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
        extras_record = self.db_manager.get_promo_extras(promo_code) or {}

        # 2. Define field partitions
        base_editable_fields = {
            'promo_notes','description','Owner','bill facing name','discount','amount','nseip_drop','dcd_web_cart',
            'product_type','bogo','fpd_display_promo','on_menu','market_group','store_group','promo_srart_date',
            'promo_end_date','comm_end_date','promo_duration','delay_time','application_grace_period','device_sales_type',
            'activation_type','active_line_required','maintain_soc','crffc_maintainactivelinedev','limit_per_ban','soc_grouping',
            'account_type','sales_application','operator_id','sku_group_id','device_status_group_id','clawback_indicator',
            'Broken_Trade','Anticipated_volume_take_rates_total','Desired_Execution'
        }
        extras_fields = {
            'jira_ticket','initiative_name','sku_link','tradein_link','promo_grace','trade_in_grace',
            'segment_name','sub_segment','segment_group_id','segment_level','flow_indicator'
        }

        base_updates = {}
        extras_updates = {}
        for k,v in promo_data.items():
            if k in base_editable_fields:
                base_updates[k] = v
            elif k in extras_fields:
                extras_updates[k] = v

        # 3. Compute old unified snapshot for diff
        unified_before = {}
        for k in base_editable_fields:
            unified_before[k] = base_record.get(k)
        for k in extras_fields:
            unified_before[k] = extras_record.get(k)

        # 4. Apply updates
        if base_updates:
            self.db_manager.update_promo_fields(promo_code, base_updates)
        if extras_updates:
            self.db_manager.upsert_promo_extras(promo_code, extras_updates, user_name)

        # 5. Fetch after state for diff
        try:
            new_base = self.db_manager.get_promo_by_code(promo_code) or {}
        except Exception:
            new_base = {}
        new_extras = self.db_manager.get_promo_extras(promo_code) or {}
        unified_after = {}
        for k in base_editable_fields:
            unified_after[k] = new_base.get(k)
        for k in extras_fields:
            unified_after[k] = new_extras.get(k)

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
            self.db_manager.record_version_entry(promo_code, 'Edit', description, user_name, diff)

        return {
            'success': True,
            'changed': changed_fields,
            'diff': diff
        }

    # --- SQL generation/version events (wrappers for previous VersionHistory integration) ---
    def record_sql_generation(self, promo_code: str, user_name: str, generation_time: float, sql_length: int):
        """Record PCR SQL generation (compact metadata only)."""
        meta = {
            'context': 'pcr',
            'sql_generation_time': generation_time,
            'sql_length': sql_length
        }
        self.db_manager.record_version_entry(promo_code, 'PCR Version', 'PCR SQL generated', user_name, meta)

    def record_date_mismatch_sql(self, promo_code: str, user_name: str, generation_time: float, sql_length: int):
        """Record Date Mismatch SQL generation (compact metadata only)."""
        meta = {
            'context': 'date_mismatch',
            'sql_generation_time': generation_time,
            'sql_length': sql_length
        }
        self.db_manager.record_version_entry(promo_code, 'Date Mismatch SQL', 'Date mismatch SQL generated', user_name, meta)

    def record_uploaded_file(self, promo_code: str, original_filename: str, stored_filename: str,
                              file_type: Optional[str], size_bytes: int, checksum: Optional[str], user_name: str):
        """Store metadata for an uploaded promo-related file."""
        self.db_manager.record_promo_file(
            code=promo_code,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_type=file_type,
            size_bytes=size_bytes,
            checksum=checksum,
            uploaded_by=user_name
        )
    
    def save_spe_promo(self, promo_code: str, promo_data: Dict[str, Any], user_name: str = "System"):
        """Save or update an SPE promotion with change tracking"""
        data = self._load_json(self.spe_file)
        
        # Add metadata
        promo_data['code'] = promo_code
        promo_data['updated_at'] = datetime.now().isoformat()
        
        # If it's a new promo, add creation timestamp
        if promo_code not in data:
            promo_data['created_at'] = datetime.now().isoformat()
            promo_data['version_history'] = [
                f"{datetime.now().strftime('%m/%d/%Y %I:%M %p')} - {user_name} - Created SPE promo."
            ]
            promo_data['last_changes'] = None
        else:
            # Preserve creation timestamp and existing permanent version history
            old_data = data[promo_code]
            promo_data['created_at'] = old_data.get('created_at', datetime.now().isoformat())
            
            # Keep permanent version history (anything that doesn't start with "Last save:")
            permanent_history = [entry for entry in old_data.get('version_history', []) 
                               if not entry.startswith('Last save:')]
            promo_data['version_history'] = permanent_history
            
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
    
    def add_permanent_version_entry(self, promo_code: str, entry: str, is_spe: bool = False):
        """Add a permanent entry to version history (for approvals, PCR versions, etc.)"""
        file_path = self.spe_file if is_spe else self.promo_file
        data = self._load_json(file_path)
        
        if promo_code in data:
            if 'version_history' not in data[promo_code]:
                data[promo_code]['version_history'] = []
            data[promo_code]['version_history'].append(entry)
            data[promo_code]['updated_at'] = datetime.now().isoformat()
            self._save_json(file_path, data)
    
    def add_approval_version(self, promo_code: str, version_number: int, approver: str, is_spe: bool = False):
        """Add an approval version entry"""
        timestamp = datetime.now().strftime('%m/%d/%Y %I:%M %p')
        entry = f"{timestamp} - {approver} - Approval sent out (version #{version_number})"
        self.add_permanent_version_entry(promo_code, entry, is_spe)
    
    def add_pcr_version(self, promo_code: str, version_number: int, user_name: str, is_spe: bool = False):
        """Add a PCR version entry"""
        timestamp = datetime.now().strftime('%m/%d/%Y %I:%M %p')
        entry = f"{timestamp} - {user_name} - PCR version #{version_number}"
        self.add_permanent_version_entry(promo_code, entry, is_spe)
    
    def delete_promo(self, promo_code: str):
        """Delete a promotion (JSON deprecated - no-op for DB)."""
        # If future: implement soft/hard delete in DB layer.
        pass

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
            'Owner': orbit_row.get('Owner') or 'Unassigned',
            'promo_srart_date': orbit_row.get('promo_srart_date'),  # note source column name consistency
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
        # Version history entry
        self.db_manager.record_version_entry(new_code, 'Create', f'Created from Orbit {orbit_id_clean}', user_name, {'orbit_id': orbit_id_clean})
        # Return unified converted record
        db_record = self.db_manager.get_promo_by_code(new_code) or {}
        payload = self.db_manager.convert_db_record_to_json_format(db_record)
        payload['success'] = True
        return payload
    
    def delete_spe_promo(self, promo_code: str):
        """Delete an SPE promotion"""
        data = self._load_json(self.spe_file)
        if promo_code in data:
            del data[promo_code]
            self._save_json(self.spe_file, data)
    
    def get_promo_list(self) -> List[Dict[str, Any]]:
        """Get a list of all promotions (DB only)."""
        all_promos = self.get_all_promos()
        now_str = datetime.now().strftime("%Y-%m-%d")
        rows: List[Dict[str, Any]] = []
        for code, promo in all_promos.items():
            end_date = promo.get('promo_end_date', '') or ''
            rows.append({
                'code': code,
                'orbit_id': promo.get('orbit_id', ''),
                'status': 'Active' if end_date > now_str else 'Expired',
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
                    'start_date': r.get('promo_srart_date',''),
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
                    'start_date': r.get('promo_srart_date',''),
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
        """Return the full SOC grouping details as formatted text."""
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
    
    def get_account_types(self) -> List[str]:
        """Get list of account type codes from account_types.txt"""
        return [
            "A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10",
            "A11", "A12", "A13", "A14", "A15", "A16", "A17", "ALL", "AT1", "AT2",
            "AT3", "AT4", "AT5", "AT6", "AT7", "GST"
        ]
    
    def get_account_type_details(self) -> str:
        """Get detailed account type information from account_types.txt"""
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
    
    def get_sales_applications(self) -> List[str]:
        """Get list of sales application codes from sales_apps.txt"""
        try:
            sales_apps_file = os.path.join(os.path.dirname(__file__), '..', 'static', 'sales_apps.txt')
            
            with open(sales_apps_file, 'r', encoding='utf-8') as file:
                content = file.read().strip()
            
            if not content:
                return []
            
            sales_apps = []
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                if line and ' - ' in line:
                    code = line.split(' - ')[0].strip()
                    if code:
                        sales_apps.append(code)
            
            return sales_apps
        except FileNotFoundError:
            print(f"Warning: sales_apps.txt file not found.")
            return []
        except Exception as e:
            print(f"Error reading sales applications: {e}")
            return []
    
    def get_sales_application_details(self) -> str:
        """Get detailed sales application information from sales_apps.txt"""
        try:
            sales_apps_file = os.path.join(os.path.dirname(__file__), '..', 'static', 'sales_apps.txt')
            
            with open(sales_apps_file, 'r', encoding='utf-8') as file:
                content = file.read().strip()
            
            if not content:
                return "No sales application information found."
            
            details = []
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if ' - ' in line:
                    parts = line.split(' - ', 1)
                    if len(parts) >= 2:
                        sales_app = parts[0].strip()
                        description = parts[1].strip()
                        
                        details.append(f"<strong>{sales_app}</strong>")
                        if description:
                            details.append(description)
                        details.append("")
                else:
                    if line:
                        # Handle lines without - separator
                        details.append(f"<strong>{line}</strong>")
                        details.append("")
            
            return "<br>".join(details)
        
        except FileNotFoundError:
            return "Sales Applications file not found."
        except Exception as e:
            return f"Error reading sales applications: {str(e)}"
    
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
            # Persist metadata in SQLite
            try:
                self.record_uploaded_file(
                    promo_code=promo_code,
                    original_filename=original_filename,
                    stored_filename=filename,
                    file_type=file_type,
                    size_bytes=file_size,
                    checksum=checksum,
                    user_name="System"
                )
            except Exception:
                pass
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
            try:
                self.record_uploaded_file(
                    promo_code=promo_code,
                    original_filename=filename,
                    stored_filename=secure_name,
                    file_type="generated_sql",
                    size_bytes=size_bytes,
                    checksum=checksum,
                    user_name="System"
                )
            except Exception:
                pass
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
                
                # Remove from metadata
                del uploaded_files[file_type]
                promo_data['uploaded_files'] = uploaded_files
                
                # Save updated promo data
                self.save_promo(promo_code, promo_data)
                
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
        """Get promotions with date mismatches between ORBIT and PAM"""
        # For now, we'll generate sample data with some date mismatches
        # When ORBIT database connection is available, this will query real data
        
        all_promos = self.get_all_promos()
        all_promo_entries = []
        owners = set()  # Track unique owners
        
        # Sample ORBIT dates to simulate mismatches (only end dates matter)
        sample_orbit_dates = {
            'P0472022': {
                'orbit_end_date': '2025-08-10'    # Different from PAM end date
            },
            'R223': {
                'orbit_end_date': '2025-07-20'    # Different from PAM end date
            }
        }
        
        for promo_code, promo_data in all_promos.items():
            # Get PAM dates
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
                'mismatch_type': 'end_date' if end_mismatch else '',
                'mismatch_severity': 'warning' if end_mismatch else '',
                'bill_facing_name': promo_data.get('bill_facing_name', ''),
                'owner': owner
            }
            
            all_promo_entries.append(promo_entry)
        
        return {
            'promos': all_promo_entries,
            'owners': sorted(list(owners))
        }