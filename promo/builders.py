# promo/builders.py
import logging
from services.jira_utils import create_jira_summary

logger = logging.getLogger(__name__)

def generate_promo_eligibility_sql(
    promo_data,
    current_user: str | None = None,
    target_env: str | None = None,
    schema: str | None = None
):
    """Generate PROMO_ELIGIBILITY_RULES INSERT statement from promo data with template header"""
    from datetime import datetime, timedelta
    import time
    import os
    
    # Import pandas at the top to avoid import delays during execution
    try:
        import pandas as pd
    except ImportError:
        pd = None
    
    # Start timing overall function
    function_start_time = time.time()

    normalized_env = (target_env or 'PROD').strip().upper()
    normalized_schema = (schema or '').strip()

    def qualify(name: str) -> str:
        if normalized_schema:
            return f"{normalized_schema}.{name}"
        return name
    
    # Check for tier compatibility conflicts before generating SQL
    # Safe normalization to avoid calling .strip() on None
    def _s(v):
        if v is None:
            return ''
        try:
            return str(v).strip()
        except Exception:
            return ''

    has_trade_data = any([
        _s(promo_data.get(f'trade_tier_{tier}_amount')) or 
        _s(promo_data.get(f'trade_tier_{tier}_make_model'))
        for tier in range(1, 5)
    ])

    has_tiered_data = (
        _s(promo_data.get('tiered_group_id')) or
        any([
            _s(promo_data.get(f'tier_{tier}_amount')) or 
            _s(promo_data.get(f'tier_{tier}_sku_group_id'))
            for tier in range(1, 5)
        ])
    )
    
    if has_trade_data and has_tiered_data:
        logger.warning("[GEN] Both trade tiers and tiered groups detected; incompatible.")
        return "-- ERROR: Cannot generate SQL - Trade-in tiers and tiered groups cannot be used together.\n-- Please clear one of the configurations before generating SQL."
    
    # Helper function to safely get integer values
    def safe_get_int(data, key, default=None):
        try:
            value = data.get(key, default)
            if value == '' or value is None:
                return default
            return int(float(value)) if isinstance(value, str) and '.' in value else int(value)
        except (ValueError, TypeError):
            return default
    
    # Helper function to format values for SQL
    def fmt_sql_value(val):
        if val is None or val == '' or str(val).upper() in ('NULL', 'NONE'):
            return 'NULL'
        if isinstance(val, str):
            if val.startswith('to_date('):
                return val
            # Escape single quotes and wrap in quotes
            return f"'{val.replace(chr(39), chr(39) + chr(39))}'"
        return str(val)
    
    # Helper function to format dates
    def fmt_date(date_str, date_type='display'):
        """
        Format dates based on type:
        - 'display': Use exact date with 20:00:00 (for DISPLAY_PROMO_START_DATE, DISPLAY_PROMO_END_DATE)
        - 'start': Subtract one day and use 20:00:00 (for PROMO_START_DATE, EFFECTIVE_DATE)
        - 'end': Add one day and use 05:00:00 (for PROMO_END_DATE, EXPIRATION_DATE)
        """
        if not date_str:
            return 'NULL'
        
        from datetime import datetime, timedelta
        
        try:
            # Parse the date string (YYYY-MM-DD format)
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            
            if date_type == 'start':
                # For start dates: subtract one day and set time to 20:00:00
                date_obj = date_obj - timedelta(days=1)
                time_str = '20:00:00'
            elif date_type == 'end':
                # For end dates: add one day and set time to 05:00:00
                date_obj = date_obj + timedelta(days=1)
                time_str = '05:00:00'
            else:  # 'display' or default
                # For display dates: use exact date with 20:00:00
                time_str = '20:00:00'
            
            formatted_date = date_obj.strftime('%Y-%m-%d')
            return f"to_date('{formatted_date} {time_str}','YYYY-MM-DD HH24:MI:SS')"
        except ValueError:
            return 'NULL'
    
    # ------------------------------------------------------------------
    # COLUMN NORMALIZATION (now resolve directly from raw DB column names)
    # We keep the original promo_data untouched and build a canonical overlay
    # so the rest of the generator can rely on stable keys.
    # ------------------------------------------------------------------
    synonyms = {
        'code': ['code','CODE','Promo Code','PROMO_CODE'],
        'orbit_id': ['orbit_id','ORBIT_ID'],
        'bill_facing_name': ['bill_facing_name','bill facing name','BILL_FACING_NAME','Bill Facing Name'],
        'promo_start_date': ['promo_start_date','promo_start_date','PROMO_START_DATE','promo_start','start_date'],
        'promo_end_date': ['promo_end_date','PROMO_END_DATE','end_date'],
        'operator_id': ['operator_id','OPERATOR_ID'],
        'sku_group_id': ['sku_group_id','SKU_GROUP_ID'],
        'soc_grouping': ['soc_grouping','SOC_GROUPING','soc_group_id','SOC_GROUP_ID'],
        'account_type': ['account_type','ACCOUNT_TYPE','atst_group_id','ATST_GROUP_ID'],
        'sales_application': ['sales_application','SALES_APPLICATION','appl_group_id','APPL_GROUP_ID'],
        'device_sales_type': ['device_sales_type','DEVICE_SALES_TYPE','device_st_group_id','DEVICE_ST_GROUP_ID'],
        'activation_type': ['activation_type','ACTIVATION_TYPE','line_st_group_id','LINE_ST_GROUP_ID'],
        'maintain_soc': ['maintain_soc','MAINTAIN_SOC','maint_soc_chk_ind','MAINT_SOC_CHK_IND'],
        'application_grace_period': ['application_grace_period','APPLICATION_GRACE_PERIOD','app_grace_group_id','APP_GRACE_GROUP_ID'],
        'trade_in_group_id': ['trade_in_group_id','trade_in_grp_id','TRADE_IN_GRP_ID','Trade_in_grp_id'],
        'trade_in_grace': ['trade_in_grace','trade_in_grace_period','TRADE_IN_GRACE_PERIOD'],
        'store_group': ['store_group','STORE_GROUP','store_grp_id','STORE_GRP_ID'],
        'market_group': ['market_group','MARKET_GROUP','market_grp_id','MARKET_GRP_ID'],
        'limit_per_ban': ['limit_per_ban','LIMIT_PER_BAN'],
        'port_in_group_id': ['port_in_group_id','PORT_IN_GROUP_ID','portin_group_id','PORTIN_GROUP_ID'],
        'discount': ['discount','DISCOUNT','promo_perc_disc','PROMO_PERC_DISC'],
        'amount': ['amount','AMOUNT','promo_amount','PROMO_AMOUNT'],
        'bptcr': ['bptcr','BPTCR','document_id','DOCUMENT_ID'],
        'min_gsm_count': ['min_gsm_count','MIN_GSM_COUNT'],
        'max_gsm_count': ['max_gsm_count','MAX_GSM_COUNT'],
        'fpd_display_promo': ['fpd_display_promo','FPD_DISPLAY_PROMO','display_promo','DISPLAY_PROMO'],
        'tiered_group_id': ['tiered_group_id','tiered_grp_id','TIERED_GRP_ID'],
        'segment_group_id': ['segment_group_id','segment_grp_id','SEGMENT_GRP_ID'],
        'product_type': ['product_type','PRODUCT_TYPE'],
        'promo_grace': ['promo_grace','PROMO_GRACE','promo_grace_period','PROMO_GRACE_PERIOD'],
        'nseip_drop': ['nseip_drop','NSEIP_DROP','nseip_drop_ind','NSEIP_DROP_IND'],
        'delay_time': ['delay_time','DELAY_TIME'],
        'mpss_lookback': ['mpss_lookback','MPSS_LOOKBACK'],
        'flow_indicator': ['flow_indicator','FLOW_INDICATOR'],
        'device_status_group_id': ['device_status_group_id','dvc_sts_grp_id','DVC_STS_GRP_ID'],
        'clawback_indicator': ['clawback_indicator','clawback_ind','CLAWBACK_IND'],
        'broken_trade': ['broken_trade','Broken_Trade','BROKEN_TRADE'],
        'segment_name': ['segment_name','SEGMENT_NAME'],
        'sub_segment': ['sub_segment','SUB_SEGMENT','sub_segment_name','SUB_SEGMENT_NAME'],
        'segment_level': ['segment_level','SEGMENT_LEVEL']
    }

    def resolve(canon_key):
        for k in synonyms.get(canon_key, []):
            if k in promo_data and promo_data.get(k) not in (None,''):
                return promo_data.get(k)
        return None

    # Build canonical overlay
    canonical = {ck: resolve(ck) for ck in synonyms.keys()}
    # Specific typo fix is now redundant thanks to synonyms but keep fallback
    if not canonical.get('promo_start_date') and promo_data.get('promo_start_date'):
        canonical['promo_start_date'] = promo_data.get('promo_start_date')
    # Merge overlay (prefer canonical values)
    merged = dict(promo_data)
    for k,v in canonical.items():
        if v is not None:
            merged[k] = v
    promo_data = merged
    # Collect critical missing fields (diagnostics only)
    critical_fields = ['code','promo_start_date','promo_end_date','bill_facing_name']
    missing_crit = [f for f in critical_fields if not promo_data.get(f)]
    logger.debug("[GEN] code=%s start=%s end=%s operator_id=%s sku_group_id=%s tiered_group_id=%s trade_in_group_id=%s", promo_data.get('code'), promo_data.get('promo_start_date'), promo_data.get('promo_end_date'), promo_data.get('operator_id'), promo_data.get('sku_group_id'), promo_data.get('tiered_group_id'), promo_data.get('trade_in_group_id'))
    if missing_crit:
        logger.debug("[GEN] Missing critical fields: %s", missing_crit)

    # Map promo data to SQL fields
    sql_values = {
        'promo_code': promo_data.get('code') if promo_data.get('code') else 'NULL',
        'promo_start_date': fmt_date(promo_data.get('promo_start_date'), 'start'),
        'promo_end_date': fmt_date(promo_data.get('promo_end_date'), 'end'),
        'operator_id': promo_data.get('operator_id') if promo_data.get('operator_id') else 'NULL',
        'promo_description': promo_data.get('bill_facing_name') if promo_data.get('bill_facing_name') else 'NULL',
        'promo_duration': safe_get_int(promo_data, 'promo_duration') if promo_data.get('promo_duration') else 'NULL',
        'promo_amount': safe_get_int(promo_data, 'amount') if promo_data.get('amount') else 'NULL',
        'effective_date': fmt_date(promo_data.get('promo_start_date'), 'start'),
        'expiration_date': fmt_date(promo_data.get('promo_end_date'), 'end'),
        'sku_group_id': promo_data.get('sku_group_id') if promo_data.get('sku_group_id') else 'NULL',
        'prim_sku_group_id': 'NULL',  # Not used in current form
        'soc_group_id': promo_data.get('soc_grouping') if promo_data.get('soc_grouping') else 'NULL',
        'atst_group_id': promo_data.get('account_type') if promo_data.get('account_type') else 'NULL',
        'appl_group_id': promo_data.get('sales_application') if promo_data.get('sales_application') else 'NULL',
        'device_st_group_id': promo_data.get('device_sales_type') if promo_data.get('device_sales_type') else 'NULL',
        'finance_type': promo_data.get('finance_type') if promo_data.get('finance_type') else 'NULL',
        'act_line_req_ind': promo_data.get('maintain_soc') if promo_data.get('maintain_soc') else 'NULL',
        'app_grace_group_id': promo_data.get('application_grace_period') if promo_data.get('application_grace_period') else 'NULL',
        'trade_in_grp_id': promo_data.get('trade_in_group_id') if promo_data.get('trade_in_group_id') else 'NULL',
        'trade_in_grace_period': promo_data.get('trade_in_grace') if promo_data.get('trade_in_grace') else 'NULL',
        'maint_act_line_chk_ind': promo_data.get('maintain_soc') if promo_data.get('maintain_soc') else 'NULL',
        'maint_soc_chk_ind': promo_data.get('maintain_soc') if promo_data.get('maintain_soc') else 'NULL',
        'store_grp_id': promo_data.get('store_group') if promo_data.get('store_group') else 'NULL',
        'market_grp_id': promo_data.get('market_group') if promo_data.get('market_group') else 'NULL',
        'limit_per_ban': safe_get_int(promo_data, 'limit_per_ban') if promo_data.get('limit_per_ban') else 'NULL',
        'tenure_group_id': 'NULL',  # Not used in current form
        'portin_group_id': promo_data.get('port_in_group_id') if promo_data.get('port_in_group_id') else 'NULL',
        'promo_perc_disc': safe_get_int(promo_data, 'discount') if promo_data.get('discount') else 'NULL',
        'c2_link': f"https://c2.t-mobile.com/offers/{promo_data.get('bptcr', '')}" if promo_data.get('bptcr') else 'NULL',
        'min_gsm_count': safe_get_int(promo_data, 'min_gsm_count') if promo_data.get('min_gsm_count') else 'NULL',
        'max_gsm_count': safe_get_int(promo_data, 'max_gsm_count') if promo_data.get('max_gsm_count') else 'NULL',
        'display_promo': promo_data.get('fpd_display_promo') if promo_data.get('fpd_display_promo') else 'NULL',
        'tiered_grp_id': promo_data.get('tiered_group_id') if promo_data.get('tiered_group_id') else 'NULL',
        'segment_grp_id': promo_data.get('segment_group_id') if promo_data.get('segment_group_id') else 'NULL',
        'bolton_trade_in_grp_id': promo_data.get('bolton_trade_in_grp_id') if promo_data.get('bolton_trade_in_grp_id') else 'NULL',
        'product_type': promo_data.get('product_type') if promo_data.get('product_type') else 'NULL',
        'pr_date': 'NULL',  # Set to NULL as requested
        'promo_grace_period': safe_get_int(promo_data, 'promo_grace') if promo_data.get('promo_grace') else 'NULL',
        'line_st_group_id': promo_data.get('activation_type') if promo_data.get('activation_type') else 'NULL',
        'nseip_drop_ind': promo_data.get('nseip_drop') if promo_data.get('nseip_drop') else 'NULL',
        'delay_time': safe_get_int(promo_data, 'delay_time') if promo_data.get('delay_time') else 'NULL',
        'display_promo_start_date': fmt_date(promo_data.get('promo_start_date'), 'display'),
        'display_promo_end_date': fmt_date(promo_data.get('promo_end_date'), 'display'),
        'mpss_lookback': safe_get_int(promo_data, 'mpss_lookback') if promo_data.get('mpss_lookback') else 'NULL',
        'flow_indicator': promo_data.get('flow_indicator') if promo_data.get('flow_indicator') else 'NULL',
        'document_id': promo_data.get('bptcr') if promo_data.get('bptcr') else 'NULL',
        'dvc_sts_grp_id': promo_data.get('device_status_group_id') if promo_data.get('device_status_group_id') else 'NULL',
        'clawback_ind': promo_data.get('clawback_indicator') if promo_data.get('clawback_indicator') else 'NULL'
    }
    
    # Format all values for SQL
    formatted_values = []
    fields = [
        'promo_code', 'promo_start_date', 'promo_end_date', 'operator_id',
        'promo_description', 'promo_duration', 'promo_amount', 'effective_date',
        'expiration_date', 'sku_group_id', 'prim_sku_group_id', 'soc_group_id', 
        'atst_group_id', 'appl_group_id', 'device_st_group_id', 'finance_type', 
        'act_line_req_ind', 'app_grace_group_id', 'trade_in_grp_id', 'trade_in_grace_period',
        'maint_act_line_chk_ind', 'maint_soc_chk_ind', 'store_grp_id', 'market_grp_id', 
        'limit_per_ban', 'tenure_group_id', 'portin_group_id', 'promo_perc_disc', 
        'c2_link', 'min_gsm_count', 'max_gsm_count', 'display_promo', 'tiered_grp_id',
        'segment_grp_id', 'bolton_trade_in_grp_id', 'product_type', 'pr_date',
        'promo_grace_period', 'line_st_group_id', 'nseip_drop_ind', 'delay_time',
        'display_promo_start_date', 'display_promo_end_date', 'mpss_lookback',
        'flow_indicator', 'document_id', 'dvc_sts_grp_id', 'clawback_ind'
    ]
    
    for field in fields:
        val = sql_values.get(field)
        if field in ['promo_start_date', 'promo_end_date', 'effective_date', 
                     'expiration_date', 'display_promo_start_date', 'display_promo_end_date']:
            formatted_values.append(val)  # Already formatted by fmt_date
        else:
            formatted_values.append(fmt_sql_value(val))
    
    # Build the SQL statement - column order must match the sample SQL exactly
    columns = [
        'RULE_ID', 'PROMO_CODE', 'PROMO_START_DATE', 'PROMO_END_DATE', 'SYS_CREATION_DATE',
        'OPERATOR_ID', 'APPLICATION_ID', 'DL_SERVICE_CODE', 'PROMO_DESCRIPTION', 'PROMO_DURATION',
        'PROMO_AMOUNT', 'EFFECTIVE_DATE', 'EXPIRATION_DATE', 'SKU_GROUP_ID', 'PRIM_SKU_GROUP_ID',
        'SOC_GROUP_ID', 'ATST_GROUP_ID', 'APPL_GROUP_ID', 'DEVICE_ST_GROUP_ID', 'FINANCE_TYPE',
        'ACT_LINE_REQ_IND', 'APP_GRACE_GROUP_ID', 'TRADE_IN_GRP_ID', 'TRADE_IN_GRACE_PERIOD',
        'MAINT_ACT_LINE_CHK_IND', 'MAINT_SOC_CHK_IND', 'STORE_GRP_ID', 'MARKET_GRP_ID',
        'LIMIT_PER_BAN', 'TENURE_GROUP_ID', 'PORTIN_GROUP_ID', 'PROMO_PERC_DISC', 'C2_LINK',
        'MIN_GSM_COUNT', 'MAX_GSM_COUNT', 'DISPLAY_PROMO', 'TIERED_GRP_ID', 'SEGMENT_GRP_ID',
        'BOLTON_TRADE_IN_GRP_ID', 'PRODUCT_TYPE', 'PR_DATE', 'PROMO_GRACE_PERIOD',
        'LINE_ST_GROUP_ID', 'NSEIP_DROP_IND', 'DELAY_TIME', 'DISPLAY_PROMO_START_DATE',
        'DISPLAY_PROMO_END_DATE', 'MPSS_LOOKBACK', 'FLOW_INDICATOR', 'DOCUMENT_ID',
        'DVC_STS_GRP_ID', 'CLAWBACK_IND'
    ]
    
    # Create the VALUES part matching the sample SQL structure
    values_list = [
        'PROMO_ELIGIBILITY_RULES_1SQ.NEXTVAL',  # RULE_ID
        formatted_values[0],  # promo_code
        formatted_values[1],  # promo_start_date
        formatted_values[2],  # promo_end_date
        'sysdate',           # SYS_CREATION_DATE
        formatted_values[3],  # operator_id
        "'CPO'",             # APPLICATION_ID
        "'USRST'",           # DL_SERVICE_CODE
        formatted_values[4],  # promo_description
        formatted_values[5],  # promo_duration
        formatted_values[6],  # promo_amount
        formatted_values[7],  # effective_date
        formatted_values[8],  # expiration_date
        formatted_values[9],  # sku_group_id
        formatted_values[10], # prim_sku_group_id
        formatted_values[11], # soc_group_id
        formatted_values[12], # atst_group_id
        formatted_values[13], # appl_group_id
        formatted_values[14], # device_st_group_id
        formatted_values[15], # finance_type
        formatted_values[16], # act_line_req_ind
        formatted_values[17], # app_grace_group_id
        formatted_values[18], # trade_in_grp_id
        formatted_values[19], # trade_in_grace_period
        formatted_values[20], # maint_act_line_chk_ind
        formatted_values[21], # maint_soc_chk_ind
        formatted_values[22], # store_grp_id
        formatted_values[23], # market_grp_id
        formatted_values[24], # limit_per_ban
        formatted_values[25], # tenure_group_id
        formatted_values[26], # portin_group_id
        formatted_values[27], # promo_perc_disc
        formatted_values[28], # c2_link
        formatted_values[29], # min_gsm_count
        formatted_values[30], # max_gsm_count
        formatted_values[31], # display_promo
        formatted_values[32], # tiered_grp_id
        formatted_values[33], # segment_grp_id
        formatted_values[34], # bolton_trade_in_grp_id
        formatted_values[35], # product_type
        formatted_values[36], # pr_date
        formatted_values[37], # promo_grace_period
        formatted_values[38], # line_st_group_id
        formatted_values[39], # nseip_drop_ind
        formatted_values[40], # delay_time
        formatted_values[41], # display_promo_start_date
        formatted_values[42], # display_promo_end_date
        formatted_values[43], # mpss_lookback
        formatted_values[44], # flow_indicator
        formatted_values[45], # document_id
        formatted_values[46], # dvc_sts_grp_id
        formatted_values[47]  # clawback_ind
    ]
    
    eligibility_table = qualify('PROMO_ELIGIBILITY_RULES')
    eligibility_seq = qualify('PROMO_ELIGIBILITY_RULES_1SQ')
    values_list[0] = f"{eligibility_seq}.NEXTVAL"

    # Generate the base SQL statement
    base_sql = f"INSERT INTO {eligibility_table} ({','.join(columns)}) VALUES ({','.join(values_list)});"
    logger.debug("[GEN][BASE_LEN] %d chars (without ancillary sections)", len(base_sql))
    
    # Create template header
    operator_id = promo_data.get('operator_id', '')
    current_user = current_user or "System"
    
    # Calculate day before launch date (promo_start_date - 1 day)
    launch_date = "DAY BEFORE LAUNCH DATE"
    if promo_data.get('promo_start_date'):
        try:
            start_date = datetime.strptime(promo_data.get('promo_start_date') or '', '%Y-%m-%d')
            day_before = start_date - timedelta(days=1)
            launch_date = day_before.strftime('%d/%m/%Y')
        except ValueError:
            pass
    
    # JIRA Summary (shared utility) and local promo_code reference needed later
    jira_summary = create_jira_summary(promo_data)
    promo_code = promo_data.get('code') or ''
    
    # Generate PROMO_TRADEIN_GROUPS INSERT statements
    def generate_tradein_groups_sql():
        tradein_sql_statements = []
        if promo_data.get('trade_in_group_id'):  # Only generate if trade_in_group_id exists
            for tier in range(1, 5):  # Tiers 1-4
                amount = promo_data.get(f'trade_tier_{tier}_amount')
                make_model = promo_data.get(f'trade_tier_{tier}_make_model')
                cond_id = promo_data.get(f'trade_tier_{tier}_cond_id')
                min_fmv = promo_data.get(f'trade_tier_{tier}_min_fmv')
                max_fmv = promo_data.get(f'trade_tier_{tier}_max_fmv')
                
                # Only create INSERT if we have required data
                if amount and make_model:
                    # Format values for SQL
                    trade_grp_id = fmt_sql_value(promo_data.get('trade_in_group_id'))
                    # Use SKU Group ID from Requirements tab instead of hardcoded 'SKU'
                    sku_group_id = promo_data.get('sku_group_id')
                    loan_sku_grp = fmt_sql_value(sku_group_id) if sku_group_id else "'SKU'"  # Fallback to 'SKU' if not provided
                    mk_mdl_grp_id = fmt_sql_value(make_model)
                    tradein_amount = amount if amount else 'NULL'
                    desc = f"'NEW PROMO - {promo_code} TIER {tier} - ${amount}'"
                    # If broken_trade is Y, force BT1; otherwise use provided cond_id or default to ST1
                    if promo_data.get('broken_trade') == 'Y':
                        trade_cond_id = "'BT1'"
                    else:
                        trade_cond_id = fmt_sql_value(cond_id) if cond_id else "'ST1'"  # Default to ST1
                    min_fmv_val = min_fmv if min_fmv else 'NULL'
                    max_fmv_val = max_fmv if max_fmv else 'NULL'
                    
                    tradein_table = qualify('PROMO_TRADEIN_GROUPS')
                    sql = f"Insert into {tradein_table} (TRADE_IN_GRP_ID, LOAN_SKU_GRP, MK_MDL_GRP_ID, SYS_CREATION_DATE,OPERATOR_ID,APPLICATION_ID,DL_SERVICE_CODE, TRADEIN_AMOUNT, TRADEIN_GROUP_DESC, TRADE_IN_COND_ID, MIN_FMV, MAX_FMV) Values ({trade_grp_id},{loan_sku_grp},{mk_mdl_grp_id},sysdate,{operator_id},'CPO','USRST',{tradein_amount},{desc},{trade_cond_id},{min_fmv_val},{max_fmv_val});"
                    tradein_sql_statements.append(sql)
        
        return '\n'.join(tradein_sql_statements) if tradein_sql_statements else ''
    
    # Generate PROMO_TRADEIN_GROUPS INSERT statements
    tradein_groups_sql = generate_tradein_groups_sql()
    if tradein_groups_sql:
        logger.debug("[GEN][TRADEIN_GROUPS] %d chars", len(tradein_groups_sql))
    
    # Generate PROMO_TIERED_GROUPS INSERT statements
    def generate_tiered_groups_sql():
        tiered_sql_statements = []
        tiered_group_id = promo_data.get('tiered_group_id', '').strip()
        
        if tiered_group_id:
            # Generate INSERT for each tier that has both amount and sku_group_id
            for tier in range(1, 5):  # Tiers 1-4
                amount = promo_data.get(f'tier_{tier}_amount', '').strip()
                sku_group_id = promo_data.get(f'tier_{tier}_sku_group_id', '').strip()
                devices = promo_data.get(f'tier_{tier}_devices', '').strip()
                
                if amount and sku_group_id:
                    # Format the description with devices info
                    desc = f"'Tier ${amount}"
                    if devices:
                        # Clean up devices text for description (limit length)
                        devices_clean = devices.replace('\n', ', ').replace('\r', '')[:100]
                        desc += f" - {devices_clean}"
                    desc += f" - {promo_code}'"
                    
                    tiered_table = qualify('PROMO_TIERED_GROUPS')
                    sql = f"Insert into {tiered_table} (TIERED_GRP_ID,SKU_GRP_ID,SYS_CREATION_DATE,OPERATOR_ID,APPLICATION_ID,DL_SERVICE_CODE,TIERED_AMOUNT,TIERED_GROUP_DESC) values ('{tiered_group_id}','{sku_group_id}',sysdate,{operator_id},'CPO','USRST',{amount},{desc});"
                    tiered_sql_statements.append(sql)
        
        return '\n'.join(tiered_sql_statements) if tiered_sql_statements else ''
    
    # Generate PROMO_TIERED_GROUPS INSERT statements
    tiered_groups_sql = generate_tiered_groups_sql()
    if tiered_groups_sql:
        logger.debug("[GEN][TIERED_GROUPS] %d chars", len(tiered_groups_sql))
    
    # Generate PROMO_DEVICE_GROUPS INSERT statements
    def generate_device_groups_sql():
        import pandas as pd
        import os
        
        device_sql_statements = []
        sku_group_id = promo_data.get('sku_group_id', '').strip()
        
        if not sku_group_id:
            return ''
        
        # Check if SKU Excel file exists
        promo_code = promo_data.get('code', '')
        if not promo_code:
            return ''
            
        # Construct path to the uploaded SKU file
        upload_dir = os.path.join('data', 'uploads', 'promotions', promo_code)
        sku_file_path = os.path.join(upload_dir, 'sku_list.xlsx')
        
        if not os.path.exists(sku_file_path):
            return ''
        
        # Check file size before processing - warn but don't block for large files
        file_size = os.path.getsize(sku_file_path)
        if file_size > 50 * 1024 * 1024:  # 50MB limit (much more generous)
            return f"-- Warning: SKU file extremely large ({file_size:,} bytes). Consider splitting the file for better performance."
        
        try:
            # Optimized Excel file reading with performance improvements
            excel_start_time = time.time()
            
            # Use more efficient pandas options for faster reading
            df = pd.read_excel(
                sku_file_path, 
                usecols=[0, 1],  # Only read first two columns
                header=None,     # No header processing
                engine='openpyxl',  # Specify engine explicitly
                nrows=10000      # Increased limit from 1000 to 10000 rows
            )
            
            excel_read_time = time.time() - excel_start_time
            
            if excel_read_time > 0.5:
                logger.debug("    Excel file read: %.2fs (%d rows)", excel_read_time, len(df))
            
            # Find the first row with actual SKU data (non-empty in both columns)
            start_row = 0
            for i in range(len(df)):
                col1_val = str(df.iloc[i, 0]).strip()
                col2_val = str(df.iloc[i, 1]).strip() if len(df.columns) > 1 else ''
                
                # Skip if either column is empty, NaN, or looks like a header
                if (col1_val and col1_val.lower() not in ['nan', 'none', ''] and 
                    col2_val and col2_val.lower() not in ['nan', 'none', ''] and
                    not any(header_word in col1_val.lower() for header_word in ['material', 'last data', 'attribute', 'report'])):
                    start_row = i
                    break
            
            # Create SKU group description
            orbit_id = promo_data.get('orbit_id', '')
            bill_facing_name = promo_data.get('bill_facing_name', '')
            sku_group_desc = f"'NEW PROMO {promo_code} - CPO-{operator_id} Orbit {orbit_id} - {bill_facing_name}'"
            
            # Process each row starting from the determined start row
            for i in range(start_row, len(df)):
                sku = str(df.iloc[i, 0]).strip()
                description = str(df.iloc[i, 1]).strip() if len(df.columns) > 1 else ''
                
                # Skip empty rows or rows with invalid data
                if not sku or sku.lower() in ['nan', 'none', ''] or not description or description.lower() in ['nan', 'none', '']:
                    continue
                
                # Clean up description for SQL (escape quotes and limit length)
                description_clean = description.replace("'", "''")[:100]
                
                # Generate base INSERT statement
                device_table = qualify('PROMO_DEVICE_GROUPS')
                base_insert = f"Insert into {device_table} (SKU_GROUP_ID,SKU,SYS_CREATION_DATE,OPERATOR_ID,APPLICATION_ID,DL_SERVICE_CODE,SKU_DESCRIPTION,SKU_GROUP_DESCRIPTION) values ('{sku_group_id}','{sku}',sysdate,{operator_id},'CPO','USRST','{description_clean}',{sku_group_desc});"
                device_sql_statements.append(base_insert)
                
                # For numeric SKUs, also generate insert with "000000" prefix
                if sku.isdigit():
                    prefixed_sku = f"000000{sku}"
                    prefixed_insert = f"Insert into {device_table} (SKU_GROUP_ID,SKU,SYS_CREATION_DATE,OPERATOR_ID,APPLICATION_ID,DL_SERVICE_CODE,SKU_DESCRIPTION,SKU_GROUP_DESCRIPTION) values ('{sku_group_id}','{prefixed_sku}',sysdate,{operator_id},'CPO','USRST','{description_clean}',{sku_group_desc});"
                    device_sql_statements.append(prefixed_insert)
        
        except Exception as e:
            # If there's an error reading the file, return empty (don't break SQL generation)
            return f"-- Error reading SKU file: {str(e)}"
        
        return '\n'.join(device_sql_statements) if device_sql_statements else ''
    
    # Generate PROMO_DEVICE_GROUPS INSERT statements
    device_start_time = time.time()
    device_groups_sql = generate_device_groups_sql()
    if device_groups_sql:
        logger.debug("[GEN][DEVICE_GROUPS] %d chars", len(device_groups_sql))
    device_time = time.time() - device_start_time
    if device_time > 1.0:
        logger.debug("  Device Groups SQL: %.2fs", device_time)

    # Generate PROMO_SEGMENT_GROUPS INSERT statements
    def generate_segment_groups_sql():
        segment_sql_statements = []
        segment_group_id = promo_data.get('segment_group_id', '').strip()
        segment_name = promo_data.get('segment_name', '').strip()
        sub_segment = promo_data.get('sub_segment', '').strip()
        segment_level = promo_data.get('segment_level', '').strip()
        
        if segment_group_id and segment_name:
            # Format values for SQL
            group_id = fmt_sql_value(segment_group_id)
            segment_name_val = fmt_sql_value(segment_name)
            sub_segment_val = fmt_sql_value(sub_segment) if sub_segment else "'NULL'"
            segment_level_val = fmt_sql_value(segment_level) if segment_level else "'BAN'"  # Default to BAN
            
            segment_table = qualify('PROMO_SEGMENT_GROUPS')
            sql = f"Insert into {segment_table} (GROUP_ID,SEGMENT_NAME,SYS_CREATION_DATE,OPERATOR_ID,APPLICATION_ID,DL_SERVICE_CODE,SUB_SEGMENT_NAME,SEGMENT_LEVEL) values ({group_id},{segment_name_val},sysdate,{operator_id},'CPO','USRST',{sub_segment_val},{segment_level_val});"
            segment_sql_statements.append(sql)
        
        return '\n'.join(segment_sql_statements) if segment_sql_statements else ''
    
    # Generate PROMO_SEGMENT_GROUPS INSERT statements
    segment_groups_sql = generate_segment_groups_sql()
    if segment_groups_sql:
        logger.debug("[GEN][SEGMENT_GROUPS] %d chars", len(segment_groups_sql))
    
    # Generate trade-in device SQL from uploaded Excel file
    def generate_tradein_device_sql():
        """Generate PROMO_MK_MDL_GROUPS SQL statements from uploaded trade-in Excel file"""
        tradein_device_sql = []
        
        # Check if trade-in SQL statements were generated from Excel upload
        if promo_data.get('tradein_sql_statements'):
            tradein_device_sql.extend(promo_data['tradein_sql_statements'])
        
        return '\n'.join(tradein_device_sql) if tradein_device_sql else ''

    # Generate trade-in device SQL statements
    tradein_device_sql = generate_tradein_device_sql()
    if tradein_device_sql and normalized_schema:
        tradein_device_sql = tradein_device_sql.replace(
            'Insert into PROMO_MK_MDL_GROUPS',
            f"Insert into {qualify('PROMO_MK_MDL_GROUPS')}"
        )
    if tradein_device_sql:
        logger.debug("[GEN][TRADEIN_DEVICE] %d chars", len(tradein_device_sql))
    
    # Generate efpe_generic_params update statement if broken_trade is Y
    efpe_update_sql = ""
    if promo_data.get('broken_trade') == 'Y':
        efpe_table = qualify('efpe_generic_params')
        efpe_update_sql = f"\n\nupdate {efpe_table} set GEN_K3 = concat(GEN_K3,',{promo_code}'), SYS_UPDATE_DATE = sysdate where gen_k1 = 'BROKEN_TRD_PROMO_IND';"
    
    # Build the complete SQL with template
    template_sql = f"""
-- User Story No. = CPO-{operator_id}
-- Requested By   = {current_user}
-- Request Date   = {launch_date}
-- Project 		  ={jira_summary}
-------------------------------------------------------------------------

-- TARGET_ENV: {normalized_env}
{f"-- PROD_SCHEMA: {normalized_schema}" if normalized_env == 'PROD' and normalized_schema else ""}
BEGIN

--PROMO_ELIGIBILITY_RULES 
{base_sql}

--PROMO_DEVICE_GROUPS
{device_groups_sql}

--PROMO_TRADEIN_GROUPS
{tradein_groups_sql}

--PROMO_TIERED_GROUPS
{tiered_groups_sql}

--PROMO_MK_MDL_GROUPS 
{tradein_device_sql}

--Promo Segment 
{segment_groups_sql}

{efpe_update_sql}
END;"""

    # Prepend diagnostics if any
    diag_lines = []
    if missing_crit:
        diag_lines.append(f"-- WARNING: Missing critical fields defaulted to NULL: {', '.join(missing_crit)}")
    if not promo_data.get('operator_id'):
        diag_lines.append("-- NOTICE: operator_id missing; OPERATOR_ID column will be NULL.")
    if not any(promo_data.get(k) for k in ['soc_grouping','account_type','sales_application']):
        diag_lines.append("-- INFO: No segmentation/grouping (SOC/Account Type/Sales Application) provided; eligibility may be broad.")
    if diag_lines:
        template_sql = '\n'.join(diag_lines) + '\n' + template_sql
    
    # End timing and log performance
    function_end_time = time.time()
    total_time = function_end_time - function_start_time
    
    # Log performance info (only print if slow)
    if total_time > 2.0:
        logger.warning("SQL Generation Performance: %.2fs, Output: %d chars", total_time, len(template_sql))

    logger.debug("[GEN][FINAL_LEN] %d chars", len(template_sql))
    return template_sql

def generate_eligibility_insert(data: dict) -> str:
    """
    Build the full INSERT for PROMO_ELIGIBILITY_RULES.
    Fields will be conditionally quoted: NULL and to_date() literals left unquoted,
    numbers unquoted, strings wrapped and escaped.
    """
    # Define the column order matching the table schema
    columns = [
        'RULE_ID', 'PROMO_CODE', 'PROMO_START_DATE', 'PROMO_END_DATE',
        'SYS_CREATION_DATE', 'OPERATOR_ID', 'APPLICATION_ID', 'DL_SERVICE_CODE',
        'PROMO_DESCRIPTION', 'PROMO_DURATION', 'PROMO_AMOUNT', 'EFFECTIVE_DATE',
        'EXPIRATION_DATE', 'SKU_GROUP_ID', 'PRIM_SKU_GROUP_ID', 'SOC_GROUP_ID',
        'ATST_GROUP_ID', 'APPL_GROUP_ID', 'DEVICE_ST_GROUP_ID', 'FINANCE_TYPE',
        'ACT_LINE_REQ_IND', 'APP_GRACE_GROUP_ID', 'TRADE_IN_GRP_ID', 'TRADE_IN_GRACE_PERIOD',
        'MAINT_ACT_LINE_CHK_IND', 'MAINT_SOC_CHK_IND', 'STORE_GRP_ID', 'MARKET_GRP_ID',
        'LIMIT_PER_BAN', 'TENURE_GROUP_ID', 'PORTIN_GROUP_ID', 'PROMO_PERC_DISC',
        'C2_LINK', 'MIN_GSM_COUNT', 'MAX_GSM_COUNT', 'DISPLAY_PROMO', 'TIERED_GRP_ID',
        'SEGMENT_GRP_ID', 'BOLTON_TRADE_IN_GRP_ID', 'PRODUCT_TYPE', 'PR_DATE',
        'PROMO_GRACE_PERIOD', 'LINE_ST_GROUP_ID', 'NSEIP_DROP_IND', 'DELAY_TIME',
        'DISPLAY_PROMO_START_DATE', 'DISPLAY_PROMO_END_DATE', 'MPSS_LOOKBACK',
        'FLOW_INDICATOR', 'DOCUMENT_ID', 'DVC_STS_GRP_ID', 'CLAWBACK_IND'
    ]

    # Formatter helper
    def fmt(val):
        if isinstance(val, str):
            if val.upper() == 'NULL':
                return 'NULL'
            if val.startswith('to_date('):
                return val
            # numeric? allow digits
            if val.isdigit():
                return val
            # else quote and escape
            return f"'{val.replace(chr(39), chr(39) + chr(39))}'"
        return str(val)

    # RULE_ID is sequence
    vals = ['PROMO_ELIGIBILITY_RULES_SEQ.NEXTVAL']
    
    # Map data keys to columns in order
    key_map = {
        'PROMO_CODE':              'promo_code',
        'PROMO_START_DATE':        'promo_start_date',
        'PROMO_END_DATE':          'promo_end_date',
        'SYS_CREATION_DATE':       'sysdate',  # Special value
        'OPERATOR_ID':             'operator_id',
        'APPLICATION_ID':          'CPO',      # Hard-coded
        'DL_SERVICE_CODE':         'USRST',    # Hard-coded
        'PROMO_DESCRIPTION':       'promo_description',
        'PROMO_DURATION':          'promo_duration',
        'PROMO_AMOUNT':            'promo_amount',
        'EFFECTIVE_DATE':          'effective_date',
        'EXPIRATION_DATE':         'expiration_date',
        'SKU_GROUP_ID':            'sku_group_id',
        'PRIM_SKU_GROUP_ID':       'prim_sku_group_id',
        'SOC_GROUP_ID':            'soc_group_id',
        'ATST_GROUP_ID':           'atst_group_id',
        'APPL_GROUP_ID':           'appl_group_id',
        'DEVICE_ST_GROUP_ID':      'device_st_group_id',
        'FINANCE_TYPE':            'finance_type',
        'ACT_LINE_REQ_IND':        'act_line_req_ind',
        'APP_GRACE_GROUP_ID':      'app_grace_group_id',
        'TRADE_IN_GRP_ID':         'trade_in_grp_id',
        'TRADE_IN_GRACE_PERIOD':   'trade_in_grace_period',
        'MAINT_ACT_LINE_CHK_IND':  'maint_act_line_chk_ind',
        'MAINT_SOC_CHK_IND':       'maint_soc_chk_ind',
        'STORE_GRP_ID':            'store_grp_id',
        'MARKET_GRP_ID':           'market_grp_id',
        'LIMIT_PER_BAN':           'limit_per_ban',
        'TENURE_GROUP_ID':         'tenure_group_id',
        'PORTIN_GROUP_ID':         'portin_group_id',
        'PROMO_PERC_DISC':         'promo_perc_disc',
        'C2_LINK':                 'c2_link',
        'MIN_GSM_COUNT':           'min_gsm_count',
        'MAX_GSM_COUNT':           'max_gsm_count',
        'DISPLAY_PROMO':           'display_promo',
        'TIERED_GRP_ID':           'tiered_grp_id',
        'SEGMENT_GRP_ID':          'segment_grp_id',
        'BOLTON_TRADE_IN_GRP_ID':  'bolton_trade_in_grp_id',
        'PRODUCT_TYPE':            'product_type',
        'PR_DATE':                 'pr_date',
        'PROMO_GRACE_PERIOD':      'promo_grace_period',
        'LINE_ST_GROUP_ID':        'line_st_group_id',
        'NSEIP_DROP_IND':          'nseip_drop_ind',
        'DELAY_TIME':              'delay_time',
        'DISPLAY_PROMO_START_DATE':'display_promo_start_date',
        'DISPLAY_PROMO_END_DATE':  'display_promo_end_date',
        'MPSS_LOOKBACK':           'mpss_lookback',
        'FLOW_INDICATOR':          'flow_indicator',
        'DOCUMENT_ID':             'document_id',
        'DVC_STS_GRP_ID':          'dvc_sts_grp_id',
        'CLAWBACK_IND':            'clawback_ind'
    }
    
    # Process columns starting from index 1 (skip RULE_ID)
    for col in columns[1:]:  # Skip RULE_ID since it's already handled
        key = key_map.get(col)
        if key == 'sysdate':
            vals.append('sysdate')
        elif key == 'CPO':
            vals.append("'CPO'")
        elif key == 'USRST':
            vals.append("'USRST'")
        elif key:
            val = data.get(key, 'NULL')
            vals.append(fmt(val))
        else:
            vals.append('NULL')

    columns_sql = ','.join(columns)
    values_sql = ','.join(vals)

    # Single-line INSERT (no newline after table name) per formatting requirement
    return f"INSERT INTO PROMO_ELIGIBILITY_RULES ({columns_sql}) VALUES ({values_sql});"





def generate_promo_insert(promo: dict) -> str:
    """
    Build the INSERT for the promo-level record.
    Expects promo dict with keys:
      - trade_in_grp_id
      - loan_sku_grp
      - mk_mdl_grp_id
      - operator_id
      - application_id
      - dl_service_code
      - tradein_amount
      - description
    """
    # sanitize single quotes in description
    desc = promo.get("description", "").replace("'", "''")

    # Single-line INSERT format
    template = ("INSERT INTO PROMO_TRADEIN_GROUPS (TRADE_IN_GRP_ID, LOAN_SKU_GRP, MK_MDL_GRP_ID, SYS_CREATION_DATE, OPERATOR_ID, APPLICATION_ID, DL_SERVICE_CODE, TRADEIN_AMOUNT, TRADEIN_GROUP_DESC) "
                "VALUES ('{grp_id}', '{loan_grp}', '{mdl_grp}', sysdate, {op_id}, '{app_id}', '{dl_code}', {amount}, '{desc}');")

    return template.format(
        grp_id=promo.get("trade_in_grp_id"),
        loan_grp=promo.get("loan_sku_grp"),
        mdl_grp=promo.get("mk_mdl_grp_id"),
        op_id=promo.get("operator_id"),
        app_id=promo.get("application_id"),
        dl_code=promo.get("dl_service_code"),
        amount=promo.get("tradein_amount"),
        desc=desc
    )


def generate_device_inserts(trade_in_grp_id: str, devices: list[dict]) -> list[str]:
    """
    Build INSERT statements for each eligible device.
    Expects:
      - trade_in_grp_id: promo group ID
      - devices: list of dicts, each with a 'sku' key
    """
    # Single-line INSERT format
    template = ("INSERT INTO PROMO_DEVICE_ELIGIBILITY (TRADE_IN_GRP_ID, DEVICE_SKU, ELIGIBLE_DATE) VALUES ('{grp_id}', '{sku}', sysdate);")

    stmts = []
    for dev in devices:
        sku = dev.get("sku")
        if not sku:
            # skip rows without a SKU
            continue
        stmts.append(template.format(grp_id=trade_in_grp_id, sku=sku))

    return stmts