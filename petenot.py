# pete_flask_single.py
import os
import re
import urllib.parse

from flask import Flask, request, redirect, url_for, flash, session, render_template
import pandas as pd
from sqlalchemy import create_engine
from jinja2 import ChoiceLoader, DictLoader

# ----------------------
# Flask setup
# ----------------------
app = Flask(__name__)
# IMPORTANT: replace with a secure random key in production (or set FLASK_SECRET_KEY env)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# ----------------------
# In-memory templates (so we can {% extends "base.html" %} in a single file)
# ----------------------
BASE_HTML = """\
<!doctype html>
<html lang="en" data-bs-theme="dark">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title or "PETE - Promo Escalation Tool" }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
      :root { --tmobile-pink: #E20074; }
      .bg-gradient { background: linear-gradient(to right, #E20074, #4B0049); min-height: 100vh; }
      .border-pink { border-color: var(--tmobile-pink) !important; }
      .neon-banner {
        background-color: rgba(0,0,0,0.66);
        border: 2px solid var(--tmobile-pink);
        box-shadow: 0 0 10px #E20074, 0 0 20px #E20074, 0 0 30px #E20074;
      }
      .chat-box { max-height: 380px; overflow-y: auto; border-top: 1px dashed #555; padding-top: .5rem; }
      .chat-msg .chat-bubble {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 14px;
        padding: .5rem .75rem;
        margin-bottom: .5rem;
        white-space: pre-wrap;
      }
    </style>
  </head>
  <body class="bg-gradient">
    <nav class="navbar navbar-expand-lg navbar-dark bg-body-tertiary border-bottom border-pink sticky-top">
      <div class="container">
        <a class="navbar-brand d-flex align-items-center gap-2" href="{{ url_for('pete') }}">
          <img src="https://i.imgur.com/oP1kjN8.png" height="36" alt="T-Mobile Logo">
          <span class="fw-bold">PETE</span>
        </a>
      </div>
    </nav>
    <main class="container py-4">
      {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
          <div class="toast-container position-fixed top-0 end-0 p-3">
            {% for category, message in messages %}
              <div class="toast align-items-center show border-0 mb-2">
                <div class="d-flex bg-{{ 'danger' if category=='danger' else 'dark' }} text-white rounded-3 shadow p-3">
                  <div class="toast-body">{{ message }}</div>
                </div>
              </div>
            {% endfor %}
          </div>
        {% endif %}
      {% endwith %}
      {% block content %}{% endblock %}
    </main>
    <footer class="text-center text-secondary small pb-4">
      Version {{ version }} | © 2025 T-Mobile Promo Ops | Built by Johnny the Python Whisperer
    </footer>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
  </body>
</html>
"""

PETE_HTML = """\
{% extends "base.html" %}
{% block content %}
<div class="neon-banner mb-4 p-3 rounded-4 d-flex align-items-center justify-content-center gap-3">
  <img src="https://i.imgur.com/oP1kjN8.png" height="48" alt="T-Mobile Logo">
  <h1 class="h3 m-0 text-white">PETE: Promo Escalation Troubleshooting Engine</h1>
</div>

<div class="row g-4">
  <!-- Chat / PETEbot -->
  <div class="col-lg-4">
    <div class="card shadow rounded-4">
      <div class="card-body">
        <h5 class="card-title">🤖 Ask PETEbot</h5>
        <form method="post" class="mb-3" autocomplete="off">
          <input type="hidden" name="form_name" value="chat_form"/>
          <div class="mb-2">
            <input type="text" name="prompt" class="form-control" placeholder="Ask about this promo... (e.g., R188 SKUs)">
          </div>
        <button class="btn btn-primary w-100">Ask</button>
        </form>
        <div class="chat-box">
          {% for msg in chat_history %}
            <div class="chat-msg {{ 'user' if msg.role=='user' else 'assistant' }}">
              <div class="small text-secondary">{{ msg.role|capitalize }}</div>
              <div class="chat-bubble">{{ msg.content }}</div>
            </div>
          {% endfor %}
        </div>
      </div>
    </div>
  </div>

  <!-- Data workflow -->
  <div class="col-lg-8">
    <div class="card shadow rounded-4">
      <div class="card-body">
        <h5 class="card-title">📘 Do you have an EIP_ID?</h5>
        <form method="post" class="row gy-2 gx-2 align-items-end">
          <input type="hidden" name="form_name" value="data_form"/>
          <div class="col-12 col-md-3">
            <label class="form-label">Mode</label>
            <select class="form-select" name="has_eip" id="has_eip" onchange="toggleMode()">
              <option value="Yes">Yes</option>
              <option value="No">No</option>
            </select>
          </div>
          <div class="col-12 col-md-5" id="eip_group">
            <label class="form-label">EIP_ID</label>
            <input type="text" class="form-control" name="eip_id" value="{{ eip_id }}">
          </div>
          <div class="col-12 col-md-5 d-none" id="ban_group">
            <label class="form-label">BAN</label>
            <input type="text" class="form-control" name="ban" placeholder="Enter BAN">
          </div>
          <div class="col-12 col-md-2">
            <button class="btn btn-success w-100">Run</button>
          </div>
        </form>

        {% if eip_df is defined and eip_df is not none and eip_df.shape[0] > 0 %}
          <hr/>
          <h6>🔍 EIP_IDs Found for This BAN</h6>
          <div class="table-responsive small">{{ eip_df.to_html(classes="table table-sm table-striped", index=False) | safe }}</div>

          <form method="post" class="row g-2 align-items-end">
            <input type="hidden" name="form_name" value="data_form"/>
            <input type="hidden" name="action" value="run_lookup_from_select"/>
            <div class="col-12 col-md-8">
              <label class="form-label">Select an EIP_ID</label>
              <select class="form-select" name="selected_eip">
                <option value="">-- choose --</option>
                {% for eid in eip_df['EQUIP_ID'].astype(str).unique() %}
                  <option value="{{ eid }}">{{ eid }}</option>
                {% endfor %}
              </select>
            </div>
            <div class="col-12 col-md-4">
              <button class="btn btn-primary w-100">Run Promo Lookup</button>
            </div>
          </form>
        {% endif %}

        {% if df_html %}
          <hr/>
          <h6>✅ Promo Data Pulled</h6>
          <div class="table-responsive small">{{ df_html|safe }}</div>
        {% endif %}

        {% if error_df_html %}
          <hr/>
          <h6>⚠️ Promo Error Reasons</h6>
          <div class="table-responsive small">{{ error_df_html|safe }}</div>
        {% endif %}

        {% if rate_plan_df_html %}
          <hr/>
          <h6>📋 Rate Plan Info (via BAN {{ used_ban }})</h6>
          <div class="table-responsive small">{{ rate_plan_df_html|safe }}</div>
        {% endif %}

        {% if aal_df_html %}
          <hr/>
          <h6>➕ Active Add-a-Line (AAL) Subscribers</h6>
          <div class="table-responsive small">{{ aal_df_html|safe }}</div>
        {% endif %}

        {% if trade_df_html %}
          <hr/>
          <h6>📦 Trade Data (QR Replica)</h6>
          <div class="table-responsive small">{{ trade_df_html|safe }}</div>
        {% elif trade_query_attempted and (order_ids|length == 0) %}
          <div class="alert alert-info mt-3">No Order Detail IDs available for Trade Data pull.</div>
        {% endif %}
      </div>
    </div>
  </div>
</div>

<script>
  function toggleMode() {
    const mode = document.getElementById('has_eip').value;
    document.getElementById('eip_group').classList.toggle('d-none', mode !== 'Yes');
    document.getElementById('ban_group').classList.toggle('d-none', mode !== 'No');
  }
  toggleMode();
</script>
{% endblock %}
"""

# Plug the dict loader into Flask/Jinja
app.jinja_loader = ChoiceLoader([
    app.jinja_loader,
    DictLoader({
        "base.html": BASE_HTML,
        "pete.html": PETE_HTML,
    })
])

# ----------------------
# Database connection
# ----------------------
def get_engine():
    """Build a SQLAlchemy engine using env vars (recommended) or hardcoded fallbacks."""
    server = os.environ.get("PETE_SQL_SERVER", "PPOLWPQMR00003,50107")
    database = os.environ.get("PETE_SQL_DATABASE", "PromoQuality")
    username = os.environ.get("PETE_SQL_USER", "Python_user")
    password = os.environ.get("PETE_SQL_PASSWORD", "Pit30&i5t#w@y45$%!")  # 🔒 move to env var in production!

    params = urllib.parse.quote_plus(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
    )
    return create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

# ----------------------
# Queries (ported from Streamlit)
# ----------------------
def get_main_data(engine, eip_id):
    query_primary = f"""
        SELECT * FROM RDC.Daily_EFPE_Basic 
        WHERE discounted_equipment_id = '{eip_id}'
    """
    df = pd.read_sql(query_primary, engine)

    if df.empty or "BAN" not in df.columns or df["BAN"].dropna().empty:
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

# ----------------------
# Helpers / PETEbot logic
# ----------------------
def deduplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    cols = pd.Series(df.columns)
    for dup in cols[cols.duplicated()].unique():
        dup_indexes = cols[cols == dup].index.tolist()
        for i, idx in enumerate(dup_indexes):
            if i == 0:
                continue
            cols[idx] = f"{cols[idx]}.{i}"
    df.columns = cols
    return df

def extract_promo_code(text: str):
    matches = re.findall(r"[A-Z]{1,4}[0-9]{2,5}", (text or "").upper())
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
        return pd.read_sql(query, engine)
    except Exception as e:
        flash(f"Failed to load promo eligibility: {e}", "danger")
        return pd.DataFrame()

def pete_response(prompt, eligibility_df: pd.DataFrame) -> str:
    p = (prompt or "").lower()
    if eligibility_df is not None and not eligibility_df.empty:
        if "sku" in p:
            skus = sorted(set(eligibility_df["SKU"].dropna()))
            return f"Eligible SKUs ({len(skus)}): {', '.join(skus)}"
        elif "soc" in p:
            socs = sorted(set(eligibility_df["SOC"].dropna()))
            return f"Eligible SOCs ({len(socs)}): {', '.join(socs)}"
        elif "segment" in p:
            segments = eligibility_df["Segment_name"].dropna().unique()
            return f"Segment(s): {', '.join(segments)}" if len(segments) > 0 else "No segment group defined."
        elif "carrier" in p:
            carriers = eligibility_df["Carrier_name"].dropna().unique()
            return f"Carrier(s): {', '.join(carriers)}" if len(carriers) > 0 else "No carrier restrictions."
        elif ("start" in p) or ("end" in p) or ("date" in p):
            start = eligibility_df["DISPLAY_PROMO_START_DATE"].dropna().astype(str).unique()
            end = eligibility_df["DISPLAY_PROMO_END_DATE"].dropna().astype(str).unique()
            if len(start) > 0 and len(end) > 0:
                return f"This promo starts on {start[0]} and ends on {end[0]}"
            else:
                return "Promo dates unavailable."
        elif any(w in p for w in ["trade", "device", "make", "model"]):
            makes = sorted(set(eligibility_df["MAKE"].dropna()))
            models = sorted(set(eligibility_df["MODEL"].dropna()))
            msg = []
            if makes:
                msg.append("Eligible trade-in makes: " + ", ".join(makes))
            if models:
                msg.append("Eligible trade-in models: " + ", ".join(models))
            return "\n".join(msg) if msg else "No specific trade-in makes or models were found in this promo."
        elif "summary" in p:
            promo_desc = (
                eligibility_df["PROMO_DESCRIPTION"].dropna().astype(str).iloc[0]
                if "PROMO_DESCRIPTION" in eligibility_df.columns and not eligibility_df["PROMO_DESCRIPTION"].dropna().empty
                else "N/A"
            )
            skus = sorted(set(eligibility_df["SKU"].dropna())) if "SKU" in eligibility_df.columns else []
            socs = sorted(set(eligibility_df["SOC"].dropna())) if "SOC" in eligibility_df.columns else []
            segments = eligibility_df["Segment_name"].dropna().unique() if "Segment_name" in eligibility_df.columns else []
            carriers = eligibility_df["Carrier_name"].dropna().unique() if "Carrier_name" in eligibility_df.columns else []
            start_s = eligibility_df["DISPLAY_PROMO_START_DATE"].dropna().astype(str) if "DISPLAY_PROMO_START_DATE" in eligibility_df.columns else pd.Series()
            end_s = eligibility_df["DISPLAY_PROMO_END_DATE"].dropna().astype(str) if "DISPLAY_PROMO_END_DATE" in eligibility_df.columns else pd.Series()
            start = start_s.iloc[0] if not start_s.empty else "N/A"
            end = end_s.iloc[0] if not end_s.empty else "N/A"
            line_st_group_ids = eligibility_df["LINE_ST_GROUP_ID"].dropna().astype(str).unique() if "LINE_ST_GROUP_ID" in eligibility_df.columns else []
            product_type = eligibility_df["PRODUCT_TYPE"].dropna().astype(str).unique() if "PRODUCT_TYPE" in eligibility_df.columns else []
            return "\n".join([
                "📦 Promo Summary:",
                f"- Description: {promo_desc}",
                f"- Start Date: {start}",
                f"- End Date: {end}",
                f"- Eligible SKUs ({len(skus)}): {', '.join(skus)}",
                f"- Eligible SOCs ({len(socs)}): {', '.join(socs)}",
                f"- Segments: {', '.join(segments)}",
                f"- Carriers: {', '.join(carriers)}",
                f"- LINE_ST_GROUP_IDs: {', '.join(line_st_group_ids)}",
                f"- Product Type: {', '.join(product_type)}",
            ])
        else:
            return "I can help with SKUs, SOCs, dates, segments, carriers, and trade devices — try asking something like 'What trades are allowed for promo R188?'"
    return "I couldn't find eligibility rules for that promo — please check the promo code or try again."

# ----------------------
# Routes
# ----------------------
@app.route("/pete", methods=["GET", "POST"])
def pete():
    # ensure session keys
    for k in ["df", "error_df", "rate_plan_df", "aal_df", "trade_df"]:
        session.setdefault(k, None)
    session.setdefault("used_ban", "")
    session.setdefault("order_ids", [])
    session.setdefault("trade_query_attempted", False)
    session.setdefault("eip_id", "")
    session.setdefault("chat_history", [])

    engine = get_engine()

    # Chat form
    if request.method == "POST" and request.form.get("form_name") == "chat_form":
        prompt = request.form.get("prompt", "")
        promo_code = extract_promo_code(prompt or "")
        eligibility_df = get_promo_eligibility_context(engine, promo_code) if promo_code else pd.DataFrame()
        chat_reply = pete_response(prompt, eligibility_df)
        session["chat_history"].append({"role": "user", "content": prompt})
        session["chat_history"].append({"role": "assistant", "content": chat_reply})
        flash("PETEbot analyzed your prompt.", "info")
        return redirect(url_for("pete"))

    # Data flow form
    if request.method == "POST" and request.form.get("form_name") == "data_form":
        mode = request.form.get("has_eip", "Yes")
        if mode == "Yes":
            eip_id = request.form.get("eip_id", "").strip()
            session["eip_id"] = eip_id
            if eip_id:
                df = get_main_data(engine, eip_id)
                session["df"] = df.to_json(orient="split")
                err = get_promo_error_reasons(engine, eip_id)
                session["error_df"] = err.to_json(orient="split")
                order_ids = df.get("ORDER_DETAIL_ID").dropna().astype(str).unique().tolist() if (not df.empty and "ORDER_DETAIL_ID" in df.columns) else []
                session["order_ids"] = order_ids
                used_ban = df.get("BAN").dropna().astype(str).iloc[0] if (not df.empty and "BAN" in df.columns and not df["BAN"].dropna().empty) else ""
                session["used_ban"] = used_ban
                if used_ban:
                    rp = get_rate_plan_data(engine, used_ban)
                    aal = get_active_aal_lines(engine, used_ban)
                    session["rate_plan_df"] = rp.to_json(orient="split")
                    session["aal_df"] = aal.to_json(orient="split")
                trade = get_trade_data_qr(engine, order_ids)
                session["trade_df"] = trade.to_json(orient="split")
                session["trade_query_attempted"] = True
                flash("Promo data pulled.", "success")
        else:
            ban = request.form.get("ban", "").strip()
            if ban:
                eip_df = get_eip_ids_by_ban(engine, ban)
                session["eip_df"] = eip_df.to_json(orient="split")
                flash("EIP_IDs loaded for BAN.", "success")

        if request.form.get("action") == "run_lookup_from_select":
            selected_eip = request.form.get("selected_eip", "").strip()
            if selected_eip:
                session["eip_id"] = selected_eip
                df = get_main_data(engine, selected_eip)
                session["df"] = df.to_json(orient="split")
                err = get_promo_error_reasons(engine, selected_eip)
                session["error_df"] = err.to_json(orient="split")
                order_ids = df.get("ORDER_DETAIL_ID").dropna().astype(str).unique().tolist() if (not df.empty and "ORDER_DETAIL_ID" in df.columns) else []
                session["order_ids"] = order_ids
                used_ban = df.get("BAN").dropna().astype(str).iloc[0] if (not df.empty and "BAN" in df.columns and not df["BAN"].dropna().empty) else session.get("used_ban", "")
                session["used_ban"] = used_ban
                if used_ban:
                    rp = get_rate_plan_data(engine, used_ban)
                    aal = get_active_aal_lines(engine, used_ban)
                    session["rate_plan_df"] = rp.to_json(orient="split")
                    session["aal_df"] = aal.to_json(orient="split")
                trade = get_trade_data_qr(engine, order_ids)
                session["trade_df"] = trade.to_json(orient="split")
                session["trade_query_attempted"] = True
                flash("Promo data pulled from selected EIP.", "success")

        return redirect(url_for("pete"))

    # Deserialize dataframes
    def load_df(key):
        js = session.get(key)
        return pd.read_json(js, orient="split") if js else pd.DataFrame()

    df = load_df("df")
    error_df = load_df("error_df")
    rate_plan_df = deduplicate_columns(load_df("rate_plan_df")) if not load_df("rate_plan_df").empty else pd.DataFrame()
    aal_df = load_df("aal_df")
    trade_df = load_df("trade_df")
    eip_df = load_df("eip_df") if session.get("eip_df") else pd.DataFrame()

    return render_template(
        "pete.html",
        title="PETE - Promo Escalation Tool",
        version="2.0.1",
        chat_history=session.get("chat_history", []),
        eip_id=session.get("eip_id", ""),
        used_ban=session.get("used_ban", ""),
        order_ids=session.get("order_ids", []),
        trade_query_attempted=session.get("trade_query_attempted", False),
        eip_df=eip_df,
        df_html=df.to_html(classes="table table-sm table-striped", index=False) if not df.empty else None,
        error_df_html=error_df.to_html(classes="table table-sm table-striped", index=False) if not error_df.empty else None,
        rate_plan_df_html=rate_plan_df.to_html(classes="table table-sm table-striped", index=False) if not rate_plan_df.empty else None,
        aal_df_html=aal_df.to_html(classes="table table-sm table-striped", index=False) if not aal_df.empty else None,
        trade_df_html=trade_df.to_html(classes="table table-sm table-striped", index=False) if not trade_df.empty else None,
    )

@app.route("/")
def home():
    return redirect(url_for("pete"))

# ----------------------
# Run
# ----------------------
if __name__ == "__main__":
    # Typical: FLASK_APP=pete_flask_single.py flask run --debug
    # Or simply:
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
