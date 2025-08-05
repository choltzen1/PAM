import json
import os
import shutil
from typing import Dict, Any, List, Optional
from datetime import datetime
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


class PromoDataManager:
    """Manages persistent storage for promotion data using JSON files"""
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.promo_file = os.path.join(data_dir, "promotions.json")
        self.spe_file = os.path.join(data_dir, "spe_promotions.json")
        self.uploads_dir = os.path.join(data_dir, "uploads")
        self.promo_uploads_dir = os.path.join(self.uploads_dir, "promotions")
        
        # Ensure directories exist
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(self.uploads_dir, exist_ok=True)
        os.makedirs(self.promo_uploads_dir, exist_ok=True)
        
        # Initialize files if they don't exist
        self._initialize_files()
    
    def _initialize_files(self):
        """Initialize JSON files with default data if they don't exist"""
        if not os.path.exists(self.promo_file):
            default_promo = {
                "P0472022": {
                    "code": "P0472022",
                    "owner": "Alejandro Ferrer",
                    "bill_facing_name": "2022 Samsung Trade P30",
                    "orbit_id": "15233",
                    "pj_code": "P047",
                    "description": "Magenta Only: Customers can get up to $600 off GS22 Series when they trade in an eligible device (new and existing customers qualify) on a qualifying rate plan - TFB Retail Only.",
                    "promo_notes": "Two-tiered discount structure.\n1. $700: All iPhones EXCEPT the iPhone 14 and 15\n2. $730: iPhone 14 and 15 (including all memory variants) to have $730\nTier 1 $730: iPhone 15, iPhone 15 Plus, iPhone 15 Pro, iPhone 15 Pro Max, iPhone 14, iPhone 14 Plus, iPhone 14 Pro, iPhone 14 Pro Max\nTier 2 $700: iPhone 15 Plus, iPhone 15 Pro, iPhone 15 Pro Max, iPhone 14 Plus, iPhone 14 Pro, iPhone 14 Pro Max, iPhone 13 Mini, iPhone 13 Pro, iPhone 13 Pro Max",
                    "discount": 10,
                    "amount": 600,
                    "nseip_drop": "N",
                    "dcd_web_cart": "Y",
                    "product_type": "G",
                    "bogo": "N",
                    "trade_in_group_id": "TRD2025-001",
                    "fpd_display_promo": "N",
                    "on_menu": "Y",
                    "market_group": "*",
                    "store_group": "*",
                    "sku_link": "https://web.powerapps.com/webplayer/iframe...",
                    "tradein_link": "https://web.powerapps.com/webplayer/iframe...",
                    "promo_start_date": "2025-07-01",
                    "promo_end_date": "2025-08-01",
                    "comm_end_date": "2025-08-15",
                    "promo_duration": 24,
                    "delay_time": 0,                    "application_grace_period": "G11",
                    "promo_grace": "",
                    "trade_in_grace": "",
                    "mpss_lookback": "",
                    "device_sales_type": "S01",
                    "activation_type": "*",
                    "maintain_soc": "Y",
                    "limit_per_ban": 4,
                    "min_gsm_count": "",
                    "max_gsm_count": 12,
                    "port_in_group_id": "G02",
                    # Segmentation fields
                    "segment_name": "",
                    "sub_segment": "",
                    "segment_group_id": "",
                    "segment_level": "",
                    # Groupings fields
                    "soc_grouping": "Group 1NS",
                    "account_type": "A01",
                    "sales_application": "S01",
                    # BPTCR fields
                    "bptcr_details": [
                        "BPTCR Detail 1",
                        "BPTCR Detail 2",
                        "BPTCR Detail 3"
                    ],
                    "version_history": [
                        "11/6/2023 1:18 PM - Michael Pugh - Approval requested for Care-Medjo, Sue, Commissions - Sandbo, Stephany and Device Finance - Kanzler, Justin.",
                        "11/1/2023 10:00 AM - Cade Holtzen - Created promo."
                    ],
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
            }
            self._save_json(self.promo_file, default_promo)
        
        if not os.path.exists(self.spe_file):
            default_spe = {
                "SP005": {
                    "code": "SP005",
                    "owner": "Hari Kariavula",
                    "bill_facing_name": "2022 Line On Us P2",
                    "orbit_id": "15600",
                    "pj_code": "SPE",
                    "description": "SPE Line On Us Promo",
                    "promo_notes": "",
                    "promo_identifier": "B",
                    "pt_priority_indicator": "G",
                    "account_type": "*",
                    "sales_application": "*",
                    "dcd_web_cart": "Y",
                    "on_menu": "N",
                    "service_priority": "2880",
                    "max_discount": "1",
                    "market_group": "*",
                    "store_group": "*",
                    "c2_content": "",
                    "promo_start_date": "2025-01-01",
                    "promo_end_date": "2025-12-31",
                    "pr_date": "",
                    "ban_tenure_start": "",
                    "ban_tenure_end": "",
                    "channel_grace_period": "NULL",
                    "maintain_line_count_days": "365",
                    "re_enroll_period": "",
                    "promo_duration": "",
                    "port_duration": "",
                    "tfb_channel_group_id": "NULL",
                    "dealer_group_id": "NULL",
                    "updated_mrc_ranking": "NULL",
                    "suppress_discount_reorder": "No",
                    "retro_ban_evaluation": "No",
                    "port_in_group_id": "NULL",
                    "adjustment_code": "EEDG74",
                    "discount_codes": "22Q12F, 22Q12P, 22Q12S",
                    "total_indicator": "N",
                    "gsm_indicator": "Y",
                    "mi_indicator": "N",
                    "pure_mi_indicator": "N",
                    "virtual_mi_indicator": "N",
                    "duplicate_indicator": "N",
                    "auto_att_indicator": "N",
                    "fax_line_indicator": "N",
                    "conference_indicator": "N",
                    "iot_indicator": "N",
                    "go_soc_group_id": "A56",
                    "bo_soc_group_id": "A55",
                    "paid_soc_group_id": "A55",
                    "min_paid_line_mi_count": "",
                    "go_line_maintenance": "A57",
                    "bo_line_maintenance": "A57",
                    "paid_line_maintenance": "A57",
                    "min_paid_line_gsm_count": "1",
                    "go_line_count": "1",
                    "bo_line_count": "1",
                    "borrow_bo_lines": "N",
                    "lend_bo_lines": "Y",
                    "soc_discount_mapping": "https://web.powerapps.com/webplayer/iframe...",
                    "version_history": [
                        f"{datetime.now().strftime('%m/%d/%Y %I:%M %p')} - Cade Holtzen - Created SPE promo."
                    ],
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                },
                "SP122": {
                    "code": "SP122",
                    "owner": "Rich Brakenhoff",
                    "bill_facing_name": "Internet ID250153",
                    "orbit_id": "23987",
                    "pj_code": "SPE",
                    "description": "Internet ID250153",
                    "promo_notes": "",
                    "promo_identifier": "F",
                    "pt_priority_indicator": "B",
                    "account_type": "A01",
                    "sales_application": "NULL",
                    "dcd_web_cart": "N",
                    "on_menu": "Y",
                    "service_priority": "2880",
                    "max_discount": "1",
                    "market_group": "*",
                    "store_group": "*",
                    "c2_content": "",
                    "promo_start_date": "2025-03-27",
                    "promo_end_date": "2025-04-02",
                    "pr_date": "",
                    "ban_tenure_start": "",
                    "ban_tenure_end": "",
                    "channel_grace_period": "G01",
                    "maintain_line_count_days": "365",
                    "re_enroll_period": "",
                    "promo_duration": "",
                    "port_duration": "",
                    "tfb_channel_group_id": "A02",
                    "dealer_group_id": "G01",
                    "updated_mrc_ranking": "GSM",
                    "suppress_discount_reorder": "Yes",
                    "retro_ban_evaluation": "No",
                    "port_in_group_id": "G03",
                    "adjustment_code": "EEDG74",
                    "discount_codes": "22Q12F, 22Q12P, 22Q12S",
                    "total_indicator": "Y",
                    "gsm_indicator": "N",
                    "mi_indicator": "Y",
                    "pure_mi_indicator": "N",
                    "virtual_mi_indicator": "N",
                    "duplicate_indicator": "N",
                    "auto_att_indicator": "Y",
                    "fax_line_indicator": "N",
                    "conference_indicator": "N",
                    "iot_indicator": "Y",
                    "go_soc_group_id": "A55",
                    "bo_soc_group_id": "A56",
                    "paid_soc_group_id": "A56",
                    "min_paid_line_mi_count": "2",
                    "go_line_maintenance": "A56",
                    "bo_line_maintenance": "A55",
                    "paid_line_maintenance": "A56",
                    "min_paid_line_gsm_count": "1",
                    "go_line_count": "2",
                    "bo_line_count": "1",
                    "borrow_bo_lines": "Y",
                    "lend_bo_lines": "N",
                    "soc_discount_mapping": "https://web.powerapps.com/webplayer/iframe...",
                    "version_history": [
                        f"{datetime.now().strftime('%m/%d/%Y %I:%M %p')} - Rich Brakenhoff - Created SPE promo."
                    ],
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
            }
            self._save_json(self.spe_file, default_spe)
    
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
        """Get a specific promotion by code"""
        data = self._load_json(self.promo_file)
        return data.get(promo_code, {})
    
    def get_spe_promo(self, promo_code: str) -> Dict[str, Any]:
        """Get a specific SPE promotion by code"""
        data = self._load_json(self.spe_file)
        return data.get(promo_code, {})
    
    def get_all_promos(self) -> Dict[str, Any]:
        """Get all promotions"""
        return self._load_json(self.promo_file)
    
    def get_paginated_promos(self, page: int = 1, per_page: int = 25, search: str = "", owner_filter: str = "all") -> Dict[str, Any]:
        """Get paginated promotions with optional filtering"""
        all_promos = self._load_json(self.promo_file)
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
    
    def get_all_spe_promos(self) -> Dict[str, Any]:
        """Get all SPE promotions"""
        return self._load_json(self.spe_file)
    
    def save_promo(self, promo_code: str, promo_data: Dict[str, Any], user_name: str = "System"):
        """Save or update a promotion with change tracking"""
        data = self._load_json(self.promo_file)
        
        # Add metadata
        promo_data['code'] = promo_code
        promo_data['updated_at'] = datetime.now().isoformat()
        
        # If it's a new promo, add creation timestamp
        if promo_code not in data:
            promo_data['created_at'] = datetime.now().isoformat()
            promo_data['version_history'] = [
                f"{datetime.now().strftime('%m/%d/%Y %I:%M %p')} - {user_name} - Created promo."
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
        self._save_json(self.promo_file, data)
    
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
        """Delete a promotion"""
        data = self._load_json(self.promo_file)
        if promo_code in data:
            del data[promo_code]
            self._save_json(self.promo_file, data)
    
    def delete_spe_promo(self, promo_code: str):
        """Delete an SPE promotion"""
        data = self._load_json(self.spe_file)
        if promo_code in data:
            del data[promo_code]
            self._save_json(self.spe_file, data)
    
    def get_promo_list(self) -> List[Dict[str, Any]]:
        """Get a list of all promotions for display in tables"""
        data = self._load_json(self.promo_file)
        return [
            {
                "code": promo_data.get("code", code),
                "orbit_id": promo_data.get("orbit_id", ""),
                "status": "Active" if promo_data.get("promo_end_date", "") > datetime.now().strftime("%Y-%m-%d") else "Expired",
                "description": promo_data.get("description", ""),
                "start_date": promo_data.get("promo_start_date", ""),
                "end_date": promo_data.get("promo_end_date", ""),
                "owner": promo_data.get("owner", "")
            }
            for code, promo_data in data.items()
        ]
    
    def get_spe_promo_list(self) -> List[Dict[str, Any]]:
        """Get a list of all SPE promotions for display in tables"""
        data = self._load_json(self.spe_file)
        return [
            {
                "code": promo_data.get("code", code),
                "orbit_id": promo_data.get("orbit_id", ""),
                "status": "Active" if promo_data.get("promo_end_date", "") > datetime.now().strftime("%Y-%m-%d") else "Expired",
                "description": promo_data.get("description", ""),
                "start_date": promo_data.get("promo_start_date", ""),
                "end_date": promo_data.get("promo_end_date", ""),                "owner": promo_data.get("owner", "")
            }
            for code, promo_data in data.items()
        ]
    
    def get_owners(self) -> List[str]:
        """Get list of unique owners from both promo types"""
        promo_data = self._load_json(self.promo_file)
        spe_data = self._load_json(self.spe_file)
        
        owners = set()
        for data in [promo_data, spe_data]:
            for promo in data.values():
                if promo.get("owner"):
                    owners.add(promo["owner"])
        
        return ["All"] + sorted(list(owners))
    
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
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Create metadata
            file_metadata = {
                "filename": filename,
                "original_name": original_filename,
                "upload_date": datetime.now().isoformat(),
                "file_size": file_size,
                "file_path": file_path
            }
            
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
    
    def get_date_mismatched_promos(self) -> List[Dict[str, Any]]:
        """Get promotions with date mismatches between ORBIT and PAM"""
        # For now, we'll generate sample data with some date mismatches
        # When ORBIT database connection is available, this will query real data
        
        all_promos = self.get_all_promos()
        mismatched_promos = []
        
        # Sample ORBIT dates to simulate mismatches
        sample_orbit_dates = {
            'P0472022': {
                'orbit_start_date': '2025-07-05',  # Different from PAM
                'orbit_end_date': '2025-08-10'    # Different from PAM
            },
            'R223': {
                'orbit_start_date': '2025-06-15',  # Different from PAM  
                'orbit_end_date': '2025-07-20'    # Different from PAM
            }
        }
        
        for promo_code, promo_data in all_promos.items():
            # Skip if no ORBIT ID
            if not promo_data.get('orbit_id'):
                continue
                
            # Get PAM dates
            pam_start = promo_data.get('promo_start_date', '')
            pam_end = promo_data.get('promo_end_date', '')
            
            # Get simulated ORBIT dates (in real implementation, this would come from ORBIT database)
            orbit_dates = sample_orbit_dates.get(promo_code, {})
            orbit_start = orbit_dates.get('orbit_start_date', pam_start)  # Default to PAM if no ORBIT data
            orbit_end = orbit_dates.get('orbit_end_date', pam_end)
            
            # Check for mismatches
            start_mismatch = orbit_start != pam_start
            end_mismatch = orbit_end != pam_end
            
            if start_mismatch or end_mismatch:
                # Determine mismatch type and severity
                if start_mismatch and end_mismatch:
                    mismatch_type = 'both'
                    mismatch_severity = 'danger'
                elif start_mismatch:
                    mismatch_type = 'start_date'
                    mismatch_severity = 'warning'
                else:
                    mismatch_type = 'end_date'
                    mismatch_severity = 'warning'
                
                # Create mismatch entry
                mismatch_entry = {
                    'code': promo_code,
                    'orbit_id': promo_data.get('orbit_id', ''),
                    'orbit_start_date': orbit_start,
                    'orbit_end_date': orbit_end,
                    'promo_start_date': pam_start,
                    'promo_end_date': pam_end,
                    'mismatch_type': mismatch_type,
                    'mismatch_severity': mismatch_severity,
                    'bill_facing_name': promo_data.get('bill_facing_name', ''),
                    'owner': promo_data.get('owner', '')
                }
                
                mismatched_promos.append(mismatch_entry)
        
        return mismatched_promos