from datetime import datetime
import pandas as pd
import os
from typing import List, Dict, Any

# --- Parser: Convert PDT one-liner into structured dict ---

def _to_oracle_date(dt: datetime) -> str:
    """
    Convert a Python datetime to an Oracle TO_DATE literal.
    """
    s = dt.strftime("%m/%d/%Y %H:%M:%S")
    return f"to_date('{s}','MM/DD/YYYY HH24:MI:SS')"


def parse_pdt_line(line: str) -> dict:
    """
    Parse the raw tab-separated PDT-exported line into a dict of fields.
    Expects exactly 48 columns (0-47) as per the PDT format.
    """
    cols = line.strip().split('\t')
    
    def parse_dt(idx: int, is_start_date: bool = False, is_end_date: bool = False) -> str:
        if idx >= len(cols):
            return 'NULL'
        raw = cols[idx]
        if raw.upper() in ('', 'NULL'):
            return 'NULL'
        try:
            # PDT uses M/D/YYYY H:MM format
            dt = datetime.strptime(raw, "%m/%d/%Y %H:%M")
            
            # Adjust time for start dates (promo_start_date and effective_date)
            if is_start_date and dt.hour == 0 and dt.minute == 0:
                dt = dt.replace(hour=20, minute=0, second=0)
            # Adjust time for end dates (promo_end_date and expiration_date)
            elif is_end_date and dt.hour == 0 and dt.minute == 0:
                dt = dt.replace(hour=5, minute=0, second=0)
            
            return _to_oracle_date(dt)
        except ValueError:
            return 'NULL'

    def safe_get(idx: int, default: str = 'NULL') -> str:
        """Safely get column value with bounds checking"""
        if idx >= len(cols):
            return default
        val = cols[idx].strip()
        return val if val and val.upper() != 'NULL' else default

    # Build the dict mapping - corrected column indices based on actual data
    return {
        'promo_code':                safe_get(0),
        'promo_start_date':          parse_dt(1, is_start_date=True),
        'promo_end_date':            parse_dt(2, is_end_date=True),
        'operator_id':               safe_get(3).split()[1] if len(safe_get(3).split()) > 1 else 'NULL',  # Extract from 'NULL    16086'
        'promo_description':         safe_get(4).replace("'", "''"),
        'promo_duration':            safe_get(5),
        'promo_amount':              safe_get(6),   # Should be column 6, not 27
        'effective_date':            parse_dt(7, is_start_date=True),   # Corrected index
        'expiration_date':           parse_dt(8, is_end_date=True),   # Corrected index
        'sku_group_id':              safe_get(9),
        'prim_sku_group_id':         safe_get(10),
        'soc_group_id':              safe_get(11),
        'atst_group_id':             safe_get(12),
        'appl_group_id':             safe_get(13),
        'device_st_group_id':        safe_get(14),
        'finance_type':              safe_get(15),
        'act_line_req_ind':          safe_get(16),
        'app_grace_group_id':        safe_get(17),
        'trade_in_grp_id':           safe_get(18),  # Corrected index
        'trade_in_grace_period':     safe_get(19),  # Corrected index
        'maint_act_line_chk_ind':    safe_get(20),
        'maint_soc_chk_ind':         safe_get(21),
        'store_grp_id':              safe_get(22),
        'market_grp_id':             safe_get(23),
        'limit_per_ban':             safe_get(24),
        'tenure_group_id':           safe_get(25),
        'portin_group_id':           safe_get(26),  # Corrected index
        'promo_perc_disc':           safe_get(27),  # Corrected index
        'c2_link':                   safe_get(28),  # Fixed - was 29, should be 28 for the URL
        'min_gsm_count':             safe_get(30),
        'max_gsm_count':             safe_get(31),
        'display_promo':             safe_get(32),
        'tiered_grp_id':             safe_get(33),
        'segment_grp_id':            safe_get(34),
        'bolton_trade_in_grp_id':    safe_get(35),
        'product_type':              safe_get(36),
        'pr_date':                   parse_dt(41),  # Corrected index
        'promo_grace_period':        safe_get(43),
        'line_st_group_id':          safe_get(44),
        'nseip_drop_ind':            safe_get(46),  # Corrected index
        'delay_time':                safe_get(47),  # Corrected index
        'display_promo_start_date':  parse_dt(41),  # Same as pr_date
        'display_promo_end_date':    parse_dt(42),
        'mpss_lookback':             safe_get(40),
        'flow_indicator':            safe_get(39),  # Corrected index
        'document_id':               safe_get(45),
        'dvc_sts_grp_id':            safe_get(37),  # Corrected index
        'clawback_ind':              safe_get(38),  # Corrected index
    }


def parse_tradein_excel(file_path: str, promo_data: Dict[str, Any]) -> List[str]:
    """
    Parse trade-in Excel file and generate SQL INSERT statements
    
    Args:
        file_path: Path to the Excel file
        promo_data: Promotion data dictionary containing necessary fields
        
    Returns:
        List of SQL INSERT statements
    """
    try:
        # Check file size before processing - warn but don't block for large files
        import os
        file_size = os.path.getsize(file_path)
        if file_size > 50 * 1024 * 1024:  # 50MB limit
            print(f"Warning: Trade-in file is very large ({file_size:,} bytes). Processing may take time.")
        
        # Read the Excel file with optimizations for large files
        df = pd.read_excel(
            file_path,
            engine='openpyxl',  # Specify engine for better performance
            nrows=50000         # Limit to 50k rows to prevent memory issues
        )
        
        # Expected columns: MAXVALUE_MFG, MAXVALUE_MODEL, MAXVALUE_DEVICE_TIER
        required_columns = ['MAXVALUE_MFG', 'MAXVALUE_MODEL', 'MAXVALUE_DEVICE_TIER'] 
        
        # Check if all required columns exist
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
        
        sql_statements = []
        
        # Get operator_id from promo data (default to 16086 if not found)
        operator_id = promo_data.get('operator_id', '16086')
        promo_code = promo_data.get('code', 'UNKNOWN')
        
        # Group devices by tier to create tier-specific make/model group IDs
        tier_groups = {}
        
        for _, row in df.iterrows():
            make = str(row['MAXVALUE_MFG']).strip().upper()
            model = str(row['MAXVALUE_MODEL']).strip()
            tier = str(row['MAXVALUE_DEVICE_TIER']).strip()
            
            # Skip empty rows
            if not make or not model or not tier or make == 'NAN' or model == 'NAN':
                continue
            
            if tier not in tier_groups:
                tier_groups[tier] = []
            
            tier_groups[tier].append({
                'make': make,
                'model': model
            })
        
        # Generate SQL statements for each tier
        for tier, devices in tier_groups.items():
            # Get the tier-specific make model group ID from promo data
            tier_field = f"trade_tier_{tier}_make_model"
            mk_mdl_grp_id = promo_data.get(tier_field, f"{promo_code}_{tier}")
            
            # Skip if no make model group ID is defined for this tier
            if not mk_mdl_grp_id or mk_mdl_grp_id.strip() == "":
                continue
            
            for device in devices:
                # Generate SQL INSERT statement
                sql_statement = f"""Insert into PROMO_MK_MDL_GROUPS (MK_MDL_GRP_ID, MAKE, MODEL, SYS_CREATION_DATE, OPERATOR_ID, APPLICATION_ID, DL_SERVICE_CODE, MK_MDL_GROUP_DESC) Values ('{mk_mdl_grp_id}','{device['make']}','{device['model']}',sysdate,{operator_id},'CPO','USRST','NEW PROMO - {promo_code} CPO-{operator_id} - TIER {tier}');"""
                
                sql_statements.append(sql_statement)
        
        return sql_statements
        
    except Exception as e:
        raise Exception(f"Error parsing trade-in Excel file: {str(e)}")


def parse_sku_excel(file_path: str, promo_data: Dict[str, Any]) -> List[str]:
    """
    Parse SKU Excel file and generate SQL INSERT statements
    
    Args:
        file_path: Path to the Excel file  
        promo_data: Promotion data dictionary containing necessary fields
        
    Returns:
        List of SQL INSERT statements
    """
    try:
        # Read the Excel file
        df = pd.read_excel(file_path)
        
        sql_statements = []
        operator_id = promo_data.get('operator_id', '16086')
        promo_code = promo_data.get('code', 'UNKNOWN')
        
        # Process SKU data (this would depend on your SKU Excel format)
        # Add your SKU processing logic here based on the actual Excel structure
        
        return sql_statements
        
    except Exception as e:
        raise Exception(f"Error parsing SKU Excel file: {str(e)}")
