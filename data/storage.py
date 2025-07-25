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
                        "11/1/2023 10:00 AM - Daniel Zhang - Created promo."
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
                        f"{datetime.now().strftime('%m/%d/%Y %I:%M %p')} - Daniel Zhang - Created SPE promo."
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
    
    def get_all_spe_promos(self) -> Dict[str, Any]:
        """Get all SPE promotions"""
        return self._load_json(self.spe_file)
    
    def save_promo(self, promo_code: str, promo_data: Dict[str, Any], user_name: str = "System"):
        """Save or update a promotion"""
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
        else:
            # Preserve creation timestamp and add to version history
            promo_data['created_at'] = data[promo_code].get('created_at', datetime.now().isoformat())
            promo_data['version_history'] = data[promo_code].get('version_history', [])
            promo_data['version_history'].append(
                f"{datetime.now().strftime('%m/%d/%Y %I:%M %p')} - {user_name} - Updated promo."
            )
        
        data[promo_code] = promo_data
        self._save_json(self.promo_file, data)
    
    def save_spe_promo(self, promo_code: str, promo_data: Dict[str, Any], user_name: str = "System"):
        """Save or update an SPE promotion"""
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
        else:
            # Preserve creation timestamp and add to version history
            promo_data['created_at'] = data[promo_code].get('created_at', datetime.now().isoformat())
            promo_data['version_history'] = data[promo_code].get('version_history', [])
            promo_data['version_history'].append(
                f"{datetime.now().strftime('%m/%d/%Y %I:%M %p')} - {user_name} - Updated SPE promo."
            )
        
        data[promo_code] = promo_data
        self._save_json(self.spe_file, data)
    
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
    
    def get_soc_groupings(self) -> Dict[str, Dict[str, Any]]:
        """Get SOC grouping definitions"""
        return {
            "Group 1NS": {
                "name": "Group 1NS - GSM - Consumer & TFB",
                "plans": [
                    "T-Mobile ONE rate plans",
                    "Magenta rate plans", 
                    "Essentials rate plans",
                    "Bus/Gov Unlimited rate plans"
                ]
            },
            "Group 3": {
                "name": "Group 3 - MI - Consumer & TFB",
                "plans": [
                    "10GB or higher Mobile Internet rate plans (limited buckets)",
                    "Excludes unlimited highspeed data plans"
                ]
            },
            "Group 4": {
                "name": "Group 4 - GSM - Consumer & TFB - excludes PlusUP & MAXUp line level upsell SOCs",
                "plans": []
            },
            "Group 5": {
                "name": "Group 5 - MI - All MTME Eligible MI/BTS - Consumer & TFB",
                "plans": []
            },
            "Group 6": {
                "name": "Group 6 - GSM - Consumer & TFB",
                "plans": [
                    "TMO ONE Plus rate plans (Incl. 55+)",
                    "Magenta Plus rate plans (Incl. First Responder & 55+)",
                    "Magenta MAX rate plans (Incl. First responder & 55+)",
                    "TMO ONE Plus Military rate plans",
                    "Magenta Plus Military rate plans",
                    "Magenta MAX Military rate plans",
                    "Business Unlimited Plus plans",
                    "Magenta Plus DHH plans",
                    "Magenta MAX DHH plans",
                    "Business Unlimited Ultimate plans",
                    "Plus Up Upsell SOCs (Include Intl/Global Plus SOCs)",
                    "MAXUp Upsell SOCs",
                    "Business Unlimited Upsell SOCs (Ultimate)"
                ]
            }
        }
    
    def get_account_types(self) -> Dict[str, List[str]]:
        """Get account type definitions"""
        return {
            "options": ["A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10"],
            "descriptions": [
                "Regular (I/R); Association (I/A); GSA (I/F); Government (I/G); MCSA (I/M)",
                "Corporate (B/C); Retail (B/L); MCSA (B/M); National (B/N); MCSAGE (B/O)",
                "Non-Profit (B/P); Sole-Proprietorship (I/S)",
                "Employee (S/Y); Non TMO Employee (S/6)"
            ]
        }
    
    def get_sales_applications(self) -> Dict[str, List[str]]:
        """Get sales application definitions"""
        return {
            "options": ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10"],
            "descriptions": [
                "Care - QVXPC; Dash (TSL) - Virtual Retail",
                "QVXPR - Retail; POS - Retail; NAT - National Retail", 
                "Web (TMO) - T-Mo.com; Web - MyT-Mo (cloud)",
                "Costco with EIP; BestBuy"
            ]
        }
    
    def get_soc_groupings(self) -> Dict[str, Dict[str, Any]]:
        """Get SOC grouping definitions"""
        return {
            "Group 1NS": {
                "name": "Group 1NS - GSM - Consumer & TFB",
                "plans": [
                    "T-Mobile ONE rate plans",
                    "Magenta rate plans", 
                    "Essentials rate plans",
                    "Bus/Gov Unlimited rate plans"
                ]
            },
            "Group 3": {
                "name": "Group 3 - MI - Consumer & TFB",
                "plans": [
                    "10GB or higher Mobile Internet rate plans (limited buckets)",
                    "Excludes unlimited highspeed data plans"
                ]
            },
            "Group 4": {
                "name": "Group 4 - GSM - Consumer & TFB - excludes PlusUP & MAXUp line level upsell SOCs",
                "plans": []
            },
            "Group 5": {
                "name": "Group 5 - MI - All MTME Eligible MI/BTS - Consumer & TFB",
                "plans": []
            },            "Group 6": {
                "name": "Group 6 - GSM - Consumer & TFB",
                "plans": [
                    "TMO ONE Plus rate plans (Incl. 55+)",
                    "Magenta Plus rate plans (Incl. First Responder & 55+)",
                    "Magenta MAX rate plans (Incl. First responder & 55+)",
                    "TMO ONE Plus Military rate plans",
                    "Magenta Plus Military rate plans",
                    "Magenta MAX Military rate plans",
                    "Business Unlimited Plus plans",
                    "Magenta Plus DHH plans",
                    "Magenta MAX DHH plans",
                    "Business Unlimited Ultimate plans",
                    "Plus Up Upsell SOCs (Include Intl/Global Plus SOCs)",
                    "MAXUp Upsell SOCs",
                    "Business Unlimited Upsell SOCs (Ultimate)"
                ]
            }
        }

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