import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import urllib
import re

# --- Page Config ---
st.set_page_config(page_title="PETE - Promo Escalation Tool", layout="centered")

# --- Session Defaults ---
if "theme" not in st.session_state:
    st.session_state["theme"] = "Dark"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
for key in ["df", "error_df", "rate_plan_df", "aal_df", "trade_df"]:
    if key not in st.session_state:
        st.session_state[key] = pd.DataFrame()
for key in ["used_ban", "order_ids"]:
    if key not in st.session_state:
        st.session_state[key] = ""
if "trade_query_attempted" not in st.session_state:
    st.session_state.trade_query_attempted = False
if "eip_id" not in st.session_state:
    st.session_state.eip_id = ""

# --- Styles & Banner ---
st.markdown(
    f"""
    <style>
    .stApp {{
        background: linear-gradient(to right, #E20074, #4B0049);
        color: {'white' if st.session_state['theme'] == 'Dark' else 'black'};
    }}
    .neon-banner {{
        display: flex;
        align-items: center;
        justify-content: center;
        background-color: #000000cc;
        border: 2px solid #E20074;
        padding: 15px;
        border-radius: 15px;
        margin-bottom: 25px;
        animation: flicker 1.5s infinite alternate;
        box-shadow: 0 0 10px #E20074, 0 0 20px #E20074, 0 0 30px #E20074;
    }}
    .neon-banner img {{
        height: 60px;
        margin-right: 15px;
    }}
    .neon-banner h1 {{
        color: #fff;
        font-size: 28px;
        text-shadow: 0 0 5px #E20074, 0 0 10px #E20074, 0 0 20px #E20074;
    }}
    @keyframes flicker {{
        0% {{opacity: 1;}}
        50% {{opacity: 0.8;}}
        100% {{opacity: 1;}}
    }}
    .footer {{
        margin-top: 50px;
        padding-top: 10px;
        text-align: center;
        font-size: 12px;
        color: #bbb;
    }}
    </style>
    <div class="neon-banner">
        <img src="https://i.imgur.com/oP1kjN8.png" alt="T-Mobile Logo">
        <h1>PETE: Promo Escalation Troubleshooting Engine</h1>
    </div>
    """,
    unsafe_allow_html=True
)

# --- DB Connection ---
def get_engine():
    server = 'PPOLWPQMR00003,50107'
    database = 'PromoQuality'
    username = 'Python_user'
    password = 'Pit30&i5t#w@y45$%!'
    params = urllib.parse.quote_plus(
        f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    )
    return create_engine(f'mssql+pyodbc:///?odbc_connect={params}')

# --- Query Functions ---
def get_main_data(engine, eip_id):
    query_primary = f"""
    SELECT * FROM RDC.Daily_EFPE_Basic 
    WHERE discounted_equipment_id = '{eip_id}'
    """
    df = pd.read_sql(query_primary, engine)

    if df.empty or "BAN" not in df.columns or df["BAN"].dropna().empty:
        st.warning("⚠️ Primary query returned no Loan Award Info — running fallback query...")
        fallback_query = f"""
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
           DECODE(acc.acc_contract_type_cd_tmo,''U'',''Upgrade'',acc.acc_jump_program_type_cd_tmo),
           acc.acc_jump_program_type_cd_tmo) AS UPGRADE_PROGRAM,   
                   acc.acc_order_line_id_tmo as ORDER_DETAIL_ID,   
                   agr.agr_source_cd as PLAN_APPLICATION_ID,
                   agr.agr_status_code as PLAN_STATUS,
                   NVL(agr.agr_start_dt,TRUNC(agr.creation_date)) as PLAN_START_DATE
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
               AND acc.acc_nbr IN (''{eip_id}'')
               AND u.account_number = acc.acc_sac_nbr
               AND u.universal_line_id = acc.acc_ulid_nbr_tmo
        ')
        """
        df = pd.read_sql(fallback_query, engine)

    return df


def get_promo_error_reasons(engine, eip_id):
    query = f"""
    SELECT * FROM openquery(PEFPEP, 'SELECT * 
    FROM EFPEBATCHPROD01O.PROMO_ERROR_REASONS 
    WHERE eip_id = ''{eip_id}''')
    ORDER BY error_reason_desc
    """
    return pd.read_sql(query, engine)

def get_rate_plan_data(engine, ban):
    query = f"""
    SELECT * FROM [ServiceAgreement].[AllData] a WITH(NOLOCK)
    INNER JOIN RDC.PETR_vRatePlans b ON a.soc = b.soc
    WHERE a.BAN = '{ban}'
    ORDER BY a.SOC_EFFECTIVE_DATE DESC
    """
    return pd.read_sql(query, engine)

def get_active_aal_lines(engine, ban):
    query = f"""
    SELECT * FROM openquery(RSCUSP, '
        SELECT * FROM VSTAPPO.SUBSCRIBER
        WHERE customer_id = ''{ban}'' AND SUB_STATUS = ''A''')
    ORDER BY paper_work_date DESC
    """
    return pd.read_sql(query, engine)

def get_trade_data_qr(engine, order_ids):
    clean_ids = [str(oid).strip() for oid in order_ids if pd.notna(oid)]
    if not clean_ids:
        return pd.DataFrame()
    formatted_ids = "', '".join(clean_ids)
    query = f"""
    SELECT * FROM [General].[Trade_Data_QR_Replica] WITH(NOLOCK)
    WHERE CAST(ord_ln_id AS VARCHAR) IN ('{formatted_ids}')
    """
    return pd.read_sql(query, engine)
    
def get_eip_ids_by_ban(engine, ban):
    ban = str(ban).strip().replace("'", "''")
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
       NVL(agr.agr_start_dt,TRUNC(agr.creation_date)) as PLAN_START_DATE,
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
      AND sac.sac_nbr = ''{ban}''
      AND u.account_number = acc.acc_sac_nbr
      AND u.universal_line_id = acc.acc_ulid_nbr_tmo')
    """
    return pd.read_sql(query, engine)

# --- Helpers ---
def deduplicate_columns(df):
    cols = pd.Series(df.columns)
    for dup in cols[cols.duplicated()].unique():
        dup_indexes = cols[cols == dup].index.tolist()
        for i, idx in enumerate(dup_indexes):
            if i == 0:
                continue
            cols[idx] = f"{cols[idx]}.{i}"
    df.columns = cols
    return df

def extract_promo_code(prompt):
    matches = re.findall(r"[A-Z]{1,4}[0-9]{2,5}", prompt.upper())
    return matches[0] if matches else None

def get_promo_eligibility_context(engine, promo_code):
    try:
        query = f"""
        WITH eligible AS (
            SELECT * 
            FROM [RDC].[Daily_EFPE_ELIGIBILITY_RULES] 
            WHERE PROMO_CODE = '{promo_code}'
        ),
        sku AS (
            SELECT b.*, a.PROMO_CODE 
            FROM eligible a
            JOIN [RDC].[Daily_EFPE_DEVICE_GROUPS] b ON a.SKU_GROUP_ID = b.SKU_GROUP_ID
        ),
        soc AS (
            SELECT c.*, a.PROMO_CODE 
            FROM eligible a
            JOIN [RDC].[Daily_EFPE_SOC_GROUPS] c ON a.SOC_GROUP_ID = c.SOC_GROUP_ID
        ),
        trade AS (
            SELECT e.*, d.TRADE_IN_GRP_ID, a.PROMO_CODE 
            FROM eligible a
            LEFT JOIN [RDC].[Daily_EFPE_TRADEIN_GROUPS] d ON a.TRADE_IN_GRP_ID = d.TRADE_IN_GRP_ID
            LEFT JOIN [RDC].[Daily_EFPE_MK_MDL_GROUPS] e ON d.MK_MDL_GRP_ID = e.MK_MDL_GRP_ID
        ),
        port AS (
            SELECT f.*, a.PROMO_CODE 
            FROM eligible a
            LEFT JOIN [RDC].[Daily_EFPE_PORT_GROUPS] f ON a.PORTIN_GROUP_ID = f.PORTIN_GROUP_ID
        ),
        segment AS (
            SELECT g.*, a.PROMO_CODE 
            FROM eligible a
            LEFT JOIN [RDC].[Daily_EFPE_SEGMENT_GROUPS] g ON a.SEGMENT_GRP_ID = g.GROUP_ID
        ),
        atst AS (
            SELECT h.*, a.PROMO_CODE 
            FROM eligible a
            JOIN [RDC].[Daily_EFPE_ATST_GROUPS] h ON a.ATST_GROUP_ID = h.GROUP_ID
        ),
        apps AS (
            SELECT i.*, a.PROMO_CODE 
            FROM eligible a
            JOIN [RDC].[Daily_EFPE_APPLICATIONS_GROUPS] i ON a.APPL_GROUP_ID = i.GROUP_ID
        )

        SELECT TOP 10000
            e.PROMO_DESCRIPTION,
            e.PROMO_CODE,
            sku.SKU,
            sku.sku_description,
            soc.SOC,
            trade.MAKE,
            trade.MODEL,
            port.Carrier_name,
            segment.Segment_name,
            atst.Account_type,
            atst.Account_sub_type,
            apps.APPL_ID,
            e.DISPLAY_PROMO_START_DATE,
            e.DISPLAY_PROMO_END_DATE,
            e.MPSS_LOOKBACK,
            e.CLAWBACK_IND,
            e.LINE_ST_GROUP_ID,
            e.PRODUCT_TYPE

        FROM eligible e
        LEFT JOIN sku ON e.PROMO_CODE = sku.PROMO_CODE
        LEFT JOIN soc ON e.PROMO_CODE = soc.PROMO_CODE
        LEFT JOIN trade ON e.PROMO_CODE = trade.PROMO_CODE
        LEFT JOIN port ON e.PROMO_CODE = port.PROMO_CODE
        LEFT JOIN segment ON e.PROMO_CODE = segment.PROMO_CODE
        LEFT JOIN atst ON e.PROMO_CODE = atst.PROMO_CODE
        LEFT JOIN apps ON e.PROMO_CODE = apps.PROMO_CODE
        """
        st.write("📥 Running eligibility SQL for promo:", promo_code)
        df = pd.read_sql(query, engine)
        st.write("📊 Retrieved rows:", len(df))
        return df
    except Exception as e:
        st.sidebar.error(f"❌ Failed to load promo eligibility: {e}")
        return pd.DataFrame()

# --- PETEbot GPT Simulated Logic (unchanged for now) ---
def get_gpt_response(prompt, df, error_df, trade_df, eligibility_df=None):
    st.write("🧠 PETEbot running actual logic")  # Moved out of sidebar to ensure it renders
    prompt = prompt.lower()

    if eligibility_df is not None and not eligibility_df.empty:

        if "sku" in prompt:
            skus = sorted(set(eligibility_df["SKU"].dropna()))
            return f"Eligible SKUs ({len(skus)}): {', '.join(skus)}"

        elif "soc" in prompt:
            socs = sorted(set(eligibility_df["SOC"].dropna()))
            return f"Eligible SOCs ({len(socs)}): {', '.join(socs)}"

        elif "segment" in prompt:
            segments = eligibility_df["Segment_name"].dropna().unique()
            return f"Segment(s): {', '.join(segments)}" if len(segments) > 0 else "No segment group defined."

        elif "carrier" in prompt:
            carriers = eligibility_df["Carrier_name"].dropna().unique()
            return f"Carrier(s): {', '.join(carriers)}" if len(carriers) > 0 else "No carrier restrictions."

        elif "start" in prompt or "end" in prompt or "date" in prompt:
            start = eligibility_df["DISPLAY_PROMO_START_DATE"].dropna().astype(str).unique()
            end = eligibility_df["DISPLAY_PROMO_END_DATE"].dropna().astype(str).unique()
            if len(start) > 0 and len(end) > 0:
                return f"This promo starts on {start[0]} and ends on {end[0]}"
            else:
                return "Promo dates unavailable."

        elif "trade" in prompt or "device" in prompt or "make" in prompt or "model" in prompt:
            makes = sorted(set(eligibility_df["MAKE"].dropna()))
            models = sorted(set(eligibility_df["MODEL"].dropna()))
            msg = ""
            if makes:
                msg += f"Eligible trade-in makes: {', '.join(makes)}\n"
            if models:
                msg += f"Eligible trade-in models: {', '.join(models)}"
            return msg if msg else "No specific trade-in makes or models were found in this promo."

        elif "summary" in prompt:
            promo_desc = eligibility_df["PROMO_DESCRIPTION"].dropna().astype(str).iloc[0] if "PROMO_DESCRIPTION" in eligibility_df.columns and not eligibility_df["PROMO_DESCRIPTION"].dropna().empty else "N/A"
            skus = sorted(set(eligibility_df["SKU"].dropna()))
            socs = sorted(set(eligibility_df["SOC"].dropna()))
            segments = eligibility_df["Segment_name"].dropna().unique()
            carriers = eligibility_df["Carrier_name"].dropna().unique()
            start = eligibility_df["DISPLAY_PROMO_START_DATE"].dropna().astype(str).iloc[0] if not eligibility_df["DISPLAY_PROMO_START_DATE"].dropna().empty else "N/A"
            end = eligibility_df["DISPLAY_PROMO_END_DATE"].dropna().astype(str).iloc[0] if not eligibility_df["DISPLAY_PROMO_END_DATE"].dropna().empty else "N/A"
            line_st_group_ids = eligibility_df["LINE_ST_GROUP_ID"].dropna().astype(str).unique()
            product_type = eligibility_df["PRODUCT_TYPE"].dropna().astype(str).unique() if "PRODUCT_TYPE" in eligibility_df.columns else []

            return (
                f"📦 Promo Summary:\n"
                f"- Description: {promo_desc}\n"
                f"- Start Date: {start}\n"
                f"- End Date: {end}\n"
                f"- Eligible SKUs ({len(skus)}): {', '.join(skus)}\n"
                f"- Eligible SOCs ({len(socs)}): {', '.join(socs)}\n"
                f"- Segments: {', '.join(segments)}\n"
                f"- Carriers: {', '.join(carriers)}\n"
                f"- LINE_ST_GROUP_IDs: {', '.join(line_st_group_ids)}\n"
                f"- Product Type: {', '.join(product_type)}"
    )


        else:
            return "I can help with SKUs, SOCs, dates, segments, carriers, and trade devices — try asking something like 'What trades are allowed for promo R188?'"

    else:
        return "I couldn't find eligibility rules for that promo — please check the promo code or try again."

# --- Main App ---
def main():
    st.sidebar.title("Options")
    theme_choice = st.sidebar.radio("Theme", ["Dark", "Light"], index=0 if st.session_state["theme"] == "Dark" else 1)
    st.session_state["theme"] = theme_choice

    st.sidebar.markdown("### 🤖 Ask PETEbot")
    for message in st.session_state.chat_history:
        with st.sidebar.chat_message(message["role"]):
            st.markdown(message["content"])

    engine = get_engine()
    prompt = st.sidebar.chat_input("Ask about this promo...")
    progress = None  # ✅ prevent UnboundLocalError if EIP section is skipped

    # --- PETEbot flow ---
    if prompt:
        try:
            st.sidebar.write("🧠 PETEbot prompt received")
            promo_code = extract_promo_code(prompt)
            st.sidebar.write("🔍 Extracted Promo Code:", promo_code)
            eligibility_df = get_promo_eligibility_context(engine, promo_code) if promo_code else pd.DataFrame()
            st.sidebar.write("📊 Rows in eligibility_df:", len(eligibility_df))
            reply = get_gpt_response(prompt, st.session_state.df, st.session_state.error_df, st.session_state.trade_df, eligibility_df)
            st.sidebar.chat_message("user").markdown(prompt)
            st.sidebar.chat_message("assistant").markdown(reply)
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
        except Exception as e:
            st.sidebar.error(f"💥 PETEbot crashed: {e}")
        st.stop()

    # --- EIP section ---
    st.subheader("Do you have an EIP_ID? 📘")
    has_eip = st.radio("Choose an option:", ["Yes", "No"])
    if has_eip == "Yes":
        st.session_state.eip_id = st.text_input("Enter EIP_ID", value=st.session_state.eip_id)
        if st.session_state.eip_id and st.session_state.df.empty:
            progress = st.progress(0, text="Starting data pull...")
            st.session_state.df = get_main_data(engine, st.session_state.eip_id)
            if progress:
                progress.progress(20, text="Promo data loaded")

            st.session_state.error_df = get_promo_error_reasons(engine, st.session_state.eip_id)
            if progress:
                progress.progress(40, text="Error reasons loaded")

            # Get Order IDs
            if "ORDER_DETAIL_ID" in st.session_state.df.columns:
                order_ids = st.session_state.df["ORDER_DETAIL_ID"].dropna().astype(str).unique()
                st.write("📦 Order IDs from promo data:", order_ids)
                st.session_state.order_ids = order_ids
            else:
                st.warning("⚠️ ORDER_DETAIL_ID column missing from data.")
                st.session_state.order_ids = []

            # Get BAN
            ban_series = st.session_state.df["BAN"].dropna().astype(str) if "BAN" in st.session_state.df.columns else pd.Series()
            st.session_state.used_ban = ban_series.iloc[0] if not ban_series.empty else ""
            if not st.session_state.used_ban:
                st.warning("⚠️ No BAN found — skipping rate plan & AAL data.")

            if st.session_state.used_ban:
                st.session_state.rate_plan_df = get_rate_plan_data(engine, st.session_state.used_ban)
                if progress:
                    progress.progress(60, text="Rate plan loaded")
                st.session_state.aal_df = get_active_aal_lines(engine, st.session_state.used_ban)
                if progress:
                    progress.progress(80, text="AAL lines loaded")

            st.session_state.trade_df = get_trade_data_qr(engine, st.session_state.order_ids)
            if progress:
                progress.progress(100, text="Trade data loaded")

            st.session_state.trade_query_attempted = True

    elif has_eip == "No":
        ban = st.text_input("Enter BAN")
        if ban and st.button("Find EIP_IDs"):
            st.session_state.eip_df = get_eip_ids_by_ban(engine, ban)

        if "eip_df" in st.session_state and not st.session_state.eip_df.empty:
            st.subheader("🔍 EIP_IDs Found for This BAN")
            st.dataframe(st.session_state.eip_df)

            selected_eip = st.selectbox(
                "Select an EIP_ID for promo data lookup",
                options=[""] + st.session_state.eip_df["EQUIP_ID"].astype(str).tolist()
            )

            if selected_eip and selected_eip != "":
                if st.button("Run Promo Lookup"):
                    st.session_state.eip_id = selected_eip
                    st.session_state.df = get_main_data(engine, selected_eip)
                    st.session_state.error_df = get_promo_error_reasons(engine, selected_eip)
                    st.session_state.order_ids = st.session_state.df["ORDER_DETAIL_ID"].dropna().astype(str).unique() if "ORDER_DETAIL_ID" in st.session_state.df.columns else []
                    st.session_state.used_ban = st.session_state.df["BAN"].dropna().astype(str).iloc[0] if "BAN" in st.session_state.df.columns else ban
                    if st.session_state.used_ban:
                        st.session_state.rate_plan_df = get_rate_plan_data(engine, st.session_state.used_ban)
                        st.session_state.aal_df = get_active_aal_lines(engine, st.session_state.used_ban)
                    st.session_state.trade_df = get_trade_data_qr(engine, st.session_state.order_ids)
                    st.session_state.trade_query_attempted = True

    # --- Display Results ---
    if not st.session_state.df.empty:
        st.success("✅ Promo Data Pulled")
        st.dataframe(st.session_state.df)

    if not st.session_state.error_df.empty:
        st.markdown("### ⚠️ Promo Error Reasons")
        st.dataframe(st.session_state.error_df)

    if not st.session_state.rate_plan_df.empty:
        st.markdown("### 📋 Rate Plan Info (via BAN)")
        st.session_state.rate_plan_df = deduplicate_columns(st.session_state.rate_plan_df)
        st.dataframe(st.session_state.rate_plan_df)

    if not st.session_state.aal_df.empty:
        st.markdown("### ➕ Active Add-a-Line (AAL) Subscribers")
        st.dataframe(st.session_state.aal_df)

    if not st.session_state.trade_df.empty:
        st.markdown("### 📦 Trade Data (QR Replica)")
        st.dataframe(st.session_state.trade_df)
    elif st.session_state.trade_query_attempted and not st.session_state.order_ids:
        st.info("No Order Detail IDs available for Trade Data pull.")

    st.markdown(
        """
        <div class="footer">
            Version 2.0.1 | © 2025 T-Mobile Promo Ops | Built by Johnny the Python Whisperer
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()

