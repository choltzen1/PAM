# promo/builders.py
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

    return (
        f"INSERT INTO PROMO_ELIGIBILITY_RULES ({columns_sql}) "
        f"VALUES ({values_sql});"
    )





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

    template = (
        "INSERT INTO PROMO_TRADEIN_GROUPS "
        "(TRADE_IN_GRP_ID, LOAN_SKU_GRP, MK_MDL_GRP_ID, "
        "SYS_CREATION_DATE, OPERATOR_ID, APPLICATION_ID, "
        "DL_SERVICE_CODE, TRADEIN_AMOUNT, TRADEIN_GROUP_DESC) "
        "VALUES ('{grp_id}', '{loan_grp}', '{mdl_grp}', "
        "sysdate, {op_id}, '{app_id}', '{dl_code}', "
        "{amount}, '{desc}');"
    )

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
    template = (
        "INSERT INTO PROMO_DEVICE_ELIGIBILITY "
        "(TRADE_IN_GRP_ID, DEVICE_SKU, ELIGIBLE_DATE) "
        "VALUES ('{grp_id}', '{sku}', sysdate);"
    )

    stmts = []
    for dev in devices:
        sku = dev.get("sku")
        if not sku:
            # skip rows without a SKU
            continue
        stmts.append(template.format(grp_id=trade_in_grp_id, sku=sku))

    return stmts