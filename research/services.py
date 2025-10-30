"""Research workspace query services (PETE functionality).
All functions return pandas DataFrames; callers may convert to dict/JSON.
"""
from typing import List
import pandas as pd
from .db import get_research_engine
import re

# --- Core Query Functions ---

def get_main_data_primary(eip_id: str) -> pd.DataFrame:
    engine = get_research_engine()
    safe = str(eip_id or '').strip().replace("'","''")
    if not safe or safe.lower() == 'none':
        return pd.DataFrame()
    query = f"""
    SELECT * FROM RDC.Daily_EFPE_Basic 
    WHERE discounted_equipment_id = '{safe}'
    """
    return pd.read_sql(query, engine)

def get_main_data_fallback(eip_id: str) -> pd.DataFrame:
    engine = get_research_engine()
    safe = str(eip_id or '').strip().replace("'","''")
    if not safe or safe.lower() == 'none':
        return pd.DataFrame()
    query = f"""
    SELECT *
    FROM openquery(OFSLL, '
        SELECT /*+ full(acc) parallel(acc,8) */
               acc.acc_nbr as EQUIP_ID,    
               ase.ase_sku_nbr_tmo as EQUIP_SKU, 
               acc.acc_status_cd_tmo as EQUIP_STATUS,
               sac.sac_nbr as BAN,
               phone_number as MSISDN, 
               acc.creation_date as EQUIP_CREATED_AT,
               DECODE(NVL(acc.acc_jump_program_type_cd_tmo,''UNDEFINED''),''UNDEFINED'',
       DECODE(acc.acc_contract_type_cd_tmo,''U'',''Upgrade'',acc.acc_jump_program_type_cd_tmo),acc.acc_jump_program_type_cd_tmo) AS UPGRADE_PROGRAM,   
               acc.acc_order_line_id_tmo as ORDER_DETAIL_ID,   
               agr.agr_source_cd as PLAN_APPLICATION_ID,
               agr.agr_status_code as PLAN_STATUS,
               NVL(agr.agr_start_dt,TRUNC(acc.creation_date)) as PLAN_START_DATE
          FROM OFSLLPROD.EDS_ACCOUNTS_TMO acc,
               OFSLLPROD.EDS_AGREEMENTS_TMO agr,
               OFSLLPROD.SUPER_ACCOUNTS_ sac,
               OFSLLPROD.ASSETS_ ase,
               DFS_ADMIN.ULID_PHONE_REF u 
         WHERE agr.agr_agreement_nbr = acc.acc_agreement_nbr_tmo
           AND acc.acc_prd_product = ''LOAN'' 
           AND sac.sac_nbr = acc.acc_sac_nbr
           AND ase.ase_aad_id = acc.acc_aad_id
           AND ase.ase_ast_type = ''H''
           AND acc.acc_nbr IN (''{safe}'')
           AND u.account_number = acc.acc_sac_nbr
           AND u.universal_line_id = acc.acc_ulid_nbr_tmo
    ')
    """
    return pd.read_sql(query, engine)

def get_main_data(eip_id: str) -> pd.DataFrame:
    primary = get_main_data_primary(eip_id)
    if primary.empty or 'BAN' not in primary.columns or primary['BAN'].dropna().empty:
        return get_main_data_fallback(eip_id)
    return primary

def get_order_detail_ids(eip_id: str) -> pd.DataFrame:
    """Fetch ORDER_DETAIL_ID for a given EIP when not present in primary dataset.
    Returns DataFrame with columns EQUIP_ID, ORDER_DETAIL_ID. Empty if none.
    """
    engine = get_research_engine()
    safe = str(eip_id).replace("'","''")
    query = f"""
    SELECT * FROM openquery(OFSLL, 'SELECT 
        acc.acc_nbr as EQUIP_ID,
        acc.acc_order_line_id_tmo as ORDER_DETAIL_ID
      FROM OFSLLPROD.EDS_ACCOUNTS_TMO acc
      WHERE acc.acc_nbr IN (''{safe}'')')
    """
    try:
        df = pd.read_sql(query, engine)
    except Exception:
        return pd.DataFrame()
    return df

def get_promo_error_reasons(eip_id: str) -> pd.DataFrame:
    engine = get_research_engine()
    safe = str(eip_id).replace("'","''")
    query = f"""
    SELECT * FROM openquery(PEFPEP, 'SELECT * 
    FROM EFPEBATCHPROD01O.PROMO_ERROR_REASONS 
    WHERE eip_id = ''{safe}''')
    ORDER BY error_reason_desc
    """
    return pd.read_sql(query, engine)

def get_rate_plan_data(ban: str) -> pd.DataFrame:
    engine = get_research_engine()
    safe = str(ban).replace("'","''")
    query = f"""
    SELECT * FROM [ServiceAgreement].[AllData] a WITH(NOLOCK)
    INNER JOIN RDC.PETR_vRatePlans b ON a.soc = b.soc
    WHERE a.BAN = '{safe}'
    ORDER BY a.SOC_EFFECTIVE_DATE DESC
    """
    return pd.read_sql(query, engine)

def get_active_aal_lines(ban: str) -> pd.DataFrame:
    engine = get_research_engine()
    safe = str(ban).replace("'","''")
    query = f"""
    SELECT * FROM openquery(RSCUSP, '
        SELECT * FROM VSTAPPO.SUBSCRIBER
        WHERE customer_id = ''{safe}'' AND SUB_STATUS = ''A''')
    ORDER BY paper_work_date DESC
    """
    return pd.read_sql(query, engine)

def get_trade_data_qr(order_ids: List[str]) -> pd.DataFrame:
    engine = get_research_engine()
    clean_ids = [str(oid).strip() for oid in order_ids if pd.notna(oid) and str(oid).strip()]
    if not clean_ids:
        return pd.DataFrame()
    formatted = "', '".join(x.replace("'","''") for x in clean_ids)
    query = f"""
    SELECT * FROM [General].[Trade_Data_QR_Replica] WITH(NOLOCK)
    WHERE CAST(ord_ln_id AS VARCHAR) IN ('{formatted}')
    """
    return pd.read_sql(query, engine)

def get_eip_ids_by_ban(ban: str) -> pd.DataFrame:
    engine = get_research_engine()
    safe = str(ban).strip().replace("'","''")
    query = f"""
    SELECT * FROM openquery(OFSLL, 'SELECT 
       acc.acc_nbr as EQUIP_ID,    
       ase.ase_sku_nbr_tmo as EQUIP_SKU, 
       acc.acc_status_cd_tmo as EQUIP_STATUS,
       sac.sac_nbr as BAN,
       phone_number as MSISDN, 
       acc.creation_date as EQUIP_CREATED_AT,
       DECODE(NVL(acc.acc_jump_program_type_cd_tmo,''UNDEFINED''),''UNDEFINED'',
       DECODE(acc.acc_contract_type_cd_tmo,''U'',''Upgrade'',acc.acc_jump_program_type_cd_tmo),acc.acc_jump_program_type_cd_tmo) as UPGRADE_PROGRAM,   
       acc.acc_order_line_id_tmo as ORDER_DETAIL_ID,   
       agr.agr_source_cd as PLAN_APPLICATION_ID,
       agr.agr_status_code as PLAN_STATUS,
       NVL(agr.agr_start_dt,TRUNC(acc.creation_date)) as PLAN_START_DATE,
       ase.ase_ast_type,
       acc.ACC_MASTER_DEALER_CD_TMO,
       ase.ASE_DESC
    FROM OFSLLPROD.EDS_ACCOUNTS_TMO acc,
         OFSLLPROD.EDS_AGREEMENTS_TMO agr,
         OFSLLPROD.SUPER_ACCOUNTS_ sac,
         OFSLLPROD.ASSETS_ ase,
         DFS_ADMIN.ULID_PHONE_REF u 
    WHERE agr_agreement_nbr = acc.acc_agreement_nbr_tmo
      AND acc.acc_prd_product = ''LOAN'' 
      AND sac.sac_nbr = acc.acc_sac_nbr
      AND ase.ase_aad_id = acc.acc_aad_id
      AND ase.ase_ast_type = ''H''
      AND sac.sac_nbr = ''{safe}''
      AND u.account_number = acc.acc_sac_nbr
      AND u.universal_line_id = acc.acc_ulid_nbr_tmo')
    """
    return pd.read_sql(query, engine)

def get_eip_ids_by_msisdn(msisdn: str) -> pd.DataFrame:
        """Lookup EIP accounts by MSISDN (phone number) mirroring BAN variant.
        Accepts raw MSISDN, strips non-digits for safety, still passes as string literal.
        """
        engine = get_research_engine()
        if msisdn is None:
                return pd.DataFrame()
        cleaned = re.sub(r"[^0-9]", "", str(msisdn))
        if not cleaned:
                return pd.DataFrame()
        safe = cleaned.replace("'","''")
        query = f"""
        SELECT * FROM openquery(OFSLL, 'SELECT 
             acc.acc_nbr as EQUIP_ID,    
             ase.ase_sku_nbr_tmo as EQUIP_SKU, 
             acc.acc_status_cd_tmo as EQUIP_STATUS,
             sac.sac_nbr as BAN,
             phone_number as MSISDN, 
             acc.creation_date as EQUIP_CREATED_AT,
             DECODE(NVL(acc.acc_jump_program_type_cd_tmo,''UNDEFINED''),''UNDEFINED'',
             DECODE(acc.acc_contract_type_cd_tmo,''U'',''Upgrade'',acc.acc_jump_program_type_cd_tmo),acc.acc_jump_program_type_cd_tmo) as UPGRADE_PROGRAM,   
             acc.acc_order_line_id_tmo as ORDER_DETAIL_ID,   
             agr.agr_source_cd as PLAN_APPLICATION_ID,
             agr.agr_status_code as PLAN_STATUS,
             NVL(agr.agr_start_dt,TRUNC(acc.creation_date)) as PLAN_START_DATE,
             ase.ase_ast_type,
             acc.ACC_MASTER_DEALER_CD_TMO,
             ase.ASE_DESC
        FROM OFSLLPROD.EDS_ACCOUNTS_TMO acc,
                 OFSLLPROD.EDS_AGREEMENTS_TMO agr,
                 OFSLLPROD.SUPER_ACCOUNTS_ sac,
                 OFSLLPROD.ASSETS_ ase,
                 DFS_ADMIN.ULID_PHONE_REF u 
        WHERE agr_agreement_nbr = acc.acc_agreement_nbr_tmo
            AND acc.acc_prd_product = ''LOAN'' 
            AND sac.sac_nbr = acc.acc_sac_nbr
            AND ase.ase_aad_id = acc.acc_aad_id
            AND ase.ase_ast_type = ''H''
            AND u.phone_number = ''{safe}''
            AND u.account_number = acc.acc_sac_nbr
            AND u.universal_line_id = acc.acc_ulid_nbr_tmo')
        """
        return pd.read_sql(query, engine)

def get_promo_eligibility_context(promo_code: str) -> pd.DataFrame:
    engine = get_research_engine()
    safe = str(promo_code).replace("'","''")
    query = f"""
    WITH eligible AS (
        SELECT * FROM [RDC].[Daily_EFPE_ELIGIBILITY_RULES] WHERE PROMO_CODE = '{safe}'
    ), sku AS (
        SELECT b.*, a.PROMO_CODE FROM eligible a JOIN [RDC].[Daily_EFPE_DEVICE_GROUPS] b ON a.SKU_GROUP_ID = b.SKU_GROUP_ID
    ), soc AS (
        SELECT c.*, a.PROMO_CODE FROM eligible a JOIN [RDC].[Daily_EFPE_SOC_GROUPS] c ON a.SOC_GROUP_ID = c.SOC_GROUP_ID
    ), trade AS (
        SELECT e.*, d.TRADE_IN_GRP_ID, a.PROMO_CODE FROM eligible a LEFT JOIN [RDC].[Daily_EFPE_TRADEIN_GROUPS] d ON a.TRADE_IN_GRP_ID = d.TRADE_IN_GRP_ID LEFT JOIN [RDC].[Daily_EFPE_MK_MDL_GROUPS] e ON d.MK_MDL_GRP_ID = e.MK_MDL_GRP_ID
    ), port AS (
        SELECT f.*, a.PROMO_CODE FROM eligible a LEFT JOIN [RDC].[Daily_EFPE_PORT_GROUPS] f ON a.PORTIN_GROUP_ID = f.PORTIN_GROUP_ID
    ), segment AS (
        SELECT g.*, a.PROMO_CODE FROM eligible a LEFT JOIN [RDC].[Daily_EFPE_SEGMENT_GROUPS] g ON a.SEGMENT_GRP_ID = g.GROUP_ID
    ), atst AS (
        SELECT h.*, a.PROMO_CODE FROM eligible a JOIN [RDC].[Daily_EFPE_ATST_GROUPS] h ON a.ATST_GROUP_ID = h.GROUP_ID
    ), apps AS (
        SELECT i.*, a.PROMO_CODE FROM eligible a JOIN [RDC].[Daily_EFPE_APPLICATIONS_GROUPS] i ON a.APPL_GROUP_ID = i.GROUP_ID
    )
    SELECT TOP 10000 e.PROMO_DESCRIPTION, e.PROMO_CODE, sku.SKU, sku.sku_description, soc.SOC, trade.MAKE, trade.MODEL, port.Carrier_name,
        segment.Segment_name, atst.Account_type, atst.Account_sub_type, apps.APPL_ID, e.DISPLAY_PROMO_START_DATE, e.DISPLAY_PROMO_END_DATE,
        e.MPSS_LOOKBACK, e.CLAWBACK_IND, e.LINE_ST_GROUP_ID, e.PRODUCT_TYPE
    FROM eligible e
    LEFT JOIN sku ON e.PROMO_CODE = sku.PROMO_CODE
    LEFT JOIN soc ON e.PROMO_CODE = soc.PROMO_CODE
    LEFT JOIN trade ON e.PROMO_CODE = trade.PROMO_CODE
    LEFT JOIN port ON e.PROMO_CODE = port.PROMO_CODE
    LEFT JOIN segment ON e.PROMO_CODE = segment.PROMO_CODE
    LEFT JOIN atst ON e.PROMO_CODE = atst.PROMO_CODE
    LEFT JOIN apps ON e.PROMO_CODE = apps.PROMO_CODE
    """
    return pd.read_sql(query, engine)

# --- Helper / Transformation ---

def deduplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = pd.Series(df.columns)
    for dup in cols[cols.duplicated()].unique():
        dup_idx = cols[cols == dup].index.tolist()
        for i, idx in enumerate(dup_idx):
            if i > 0:
                cols[idx] = f"{cols[idx]}.{i}"
    df.columns = cols
    return df

PROMO_CODE_PATTERN = re.compile(r"[A-Z]{1,4}[0-9]{2,5}")

def extract_promo_code(prompt: str):
    m = PROMO_CODE_PATTERN.findall(prompt.upper())
    return m[0] if m else None

# --- PETE Chat Response Logic (Flask adaptation) ---
def generate_pete_response(prompt: str, eligibility_df: pd.DataFrame | None) -> str:
    """Simplified version of PETEbot logic operating on eligibility dataframe.
    Supports queries about SKU, SOC, segment, carrier, dates, trade devices, summary.
    """
    prompt_low = prompt.lower()
    if eligibility_df is None or eligibility_df.empty:
        return "I couldn't find eligibility rules for that promo — check the promo code or try again."

    def uniq(col):
        if col not in eligibility_df.columns:
            return []
        return [str(x) for x in eligibility_df[col].dropna().unique() if str(x).strip()]

    if any(k in prompt_low for k in ["sku", "skus"]):
        skus = uniq("SKU")
        return f"Eligible SKUs ({len(skus)}): {', '.join(skus)}" if skus else "No SKUs found." 

    if "soc" in prompt_low:
        socs = uniq("SOC")
        return f"Eligible SOCs ({len(socs)}): {', '.join(socs)}" if socs else "No SOCs found." 

    if "segment" in prompt_low:
        segments = uniq("Segment_name")
        return f"Segments: {', '.join(segments)}" if segments else "No segment group defined." 

    if "carrier" in prompt_low:
        carriers = uniq("Carrier_name")
        return f"Carriers: {', '.join(carriers)}" if carriers else "No carrier restrictions." 

    if any(k in prompt_low for k in ["start", "end", "date"]):
        start = uniq("DISPLAY_PROMO_START_DATE")
        end = uniq("DISPLAY_PROMO_END_DATE")
        if start and end:
            return f"This promo starts on {start[0]} and ends on {end[0]}"
        return "Promo dates unavailable." 

    if any(k in prompt_low for k in ["trade", "device", "make", "model"]):
        makes = uniq("MAKE")
        models = uniq("MODEL")
        msg = []
        if makes:
            msg.append(f"Eligible trade-in makes: {', '.join(makes)}")
        if models:
            msg.append(f"Eligible trade-in models: {', '.join(models)}")
        return "\n".join(msg) if msg else "No specific trade-in makes or models found." 

    if "summary" in prompt_low:
        desc = uniq("PROMO_DESCRIPTION")
        skus = uniq("SKU")
        socs = uniq("SOC")
        segments = uniq("Segment_name")
        carriers = uniq("Carrier_name")
        line_st = uniq("LINE_ST_GROUP_ID")
        product_type = uniq("PRODUCT_TYPE")
        start = uniq("DISPLAY_PROMO_START_DATE")
        end = uniq("DISPLAY_PROMO_END_DATE")
        return (
            "\n".join([
                "\ud83d\udce6 Promo Summary:",
                f"- Description: {desc[0] if desc else 'N/A'}",
                f"- Start Date: {start[0] if start else 'N/A'}",
                f"- End Date: {end[0] if end else 'N/A'}",
                f"- Eligible SKUs ({len(skus)}): {', '.join(skus) if skus else 'None'}",
                f"- Eligible SOCs ({len(socs)}): {', '.join(socs) if socs else 'None'}",
                f"- Segments: {', '.join(segments) if segments else 'None'}",
                f"- Carriers: {', '.join(carriers) if carriers else 'None'}",
                f"- LINE_ST_GROUP_IDs: {', '.join(line_st) if line_st else 'None'}",
                f"- Product Type: {', '.join(product_type) if product_type else 'None'}",
            ])
        )

    return "Ask about SKUs, SOCs, segments, carriers, dates, trade devices, or 'summary'."

