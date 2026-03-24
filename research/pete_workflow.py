"""Simplified PETE workflow recreation.

Responsibilities:
 - Maintain session state for EIP promo data, derived BAN, ancillary datasets.
 - Provide BAN-based EIP discovery list.
 - Execute primary + fallback main data queries (via services module).
 - Persist chat history and generate responses using promo eligibility subset.
"""

from typing import Dict, List, Any
from io import StringIO
import pandas as pd
from flask import session
from .services import (
    get_main_data_primary,
    get_main_data_fallback,
    get_promo_error_reasons,
    get_rate_plan_data,
    get_active_aal_lines,
    get_trade_data_qr,
    get_eip_ids_by_ban,
    get_promo_eligibility_context,
    deduplicate_columns,
    extract_promo_code,
    generate_pete_response,
    get_order_detail_ids,
)

SESSION_KEYS = [
    "df_main", "promo_errors", "rate_plans", "aal_lines", "trade_data", "eip_list",
    "used_ban", "eip_id", "order_ids", "trade_query_attempted", "chat_history",
    "last_mode", "last_ban", "eip_list_attempted", "main_fallback_used", "missing_ban", "missing_order_ids"
]

def ensure_session_defaults():
    for k in SESSION_KEYS:
        if k in ("chat_history", "order_ids"):
            session.setdefault(k, [])
        else:
            session.setdefault(k, None)
    session.setdefault("used_ban", "")
    session.setdefault("trade_query_attempted", False)
    session.setdefault("last_mode", "")
    session.setdefault("last_ban", "")
    session.setdefault("eip_list_attempted", False)
    session.setdefault("main_fallback_used", False)
    session.setdefault("missing_ban", False)
    session.setdefault("missing_order_ids", False)


def clear_pete_query_state(*, keep_chat_history: bool = True, keep_discovery: bool = False) -> None:
    """Clear prior PETE query outputs from the session.

    PETE uses PRG (POST-redirect-GET) and stores results in the session. When the
    user runs a new lookup (or selects a different EIP_ID), we want the page to
    reflect only the latest search.

    Args:
        keep_chat_history: Preserve chat transcript state.
        keep_discovery: Preserve BAN discovery list (EIP IDs) + last BAN.
    """
    keys_to_clear = [
        'df_main',
        'promo_errors',
        'rate_plans',
        'aal_lines',
        'trade_data',
        'used_ban',
        'eip_id',
        'main_fallback_used',
        'missing_ban',
        'missing_order_ids',
    ]
    if not keep_chat_history:
        keys_to_clear.append('chat_history')
    if not keep_discovery:
        keys_to_clear.extend(['eip_list', 'eip_list_attempted', 'last_ban'])

    for k in keys_to_clear:
        session.pop(k, None)

    # Normalize a few stateful flags/containers back to safe defaults.
    session['order_ids'] = []
    session['trade_query_attempted'] = False

    if not keep_discovery:
        session.setdefault('eip_list_attempted', False)
        session.setdefault('last_ban', '')

def _encode_df(df: pd.DataFrame | None) -> str | None:
    if df is None or df.empty:
        return None
    return df.to_json(orient="split")

def _decode_df(raw: Any) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame()
    try:
        if isinstance(raw, str):
            return pd.read_json(StringIO(raw), orient="split")
        return pd.read_json(raw, orient="split")
    except Exception:
        return pd.DataFrame()

DATE_COL_HINTS = [
    "DATE",        # generic date
    "_DATE",       # explicit suffix
    "DT",          # short datetime marker
    "TIME",        # time columns
    "CREATED",     # creation timestamps
    "EFFECTIVE",   # effective period start
    "EXPIRATION",  # expiration markers
    "ISSUE_DATE",  # issue dates
    "UPDATED",     # last updated
    "UPDATE",      # alternate update
    "START",       # start date/time
    "END"          # end date/time
]

EXCLUDE_EXACT = {
    'ID', 'EQUIP_ID', 'DISCOUNTED_EQUIPMENT_ID', 'ORDER_DETAIL_ID',
    'PLAN_APPLICATION_ID', 'LINE_ST_GROUP_ID'
}

# Columns that should always be treated as epoch timestamps even if they lack standard date hints.
# Add headers here (uppercase) as needed when source systems deliver them as numeric epochs.
FORCE_DATETIME_COLUMNS = {
    'START_DATE',
    'EXPIRATION_DATE',
    'CREATED_AT',
    'UPDATED_AT',
    'LAST_EVENT_OCCURRED_ON',
    'LAST_EVENT_OCCURRED',
    'EQUIP_CREATED_AT',
    'EIP_PLAN_START_DATE',
    'SYS_CREATION_DATE',
    'SYS_UPDATE_DATE',
    'SOC_EFFECTIVE_DATE',
    'SOC_EFFECTIVE_ISSUE_DATE',
    'SOC_EXPIRATION_DATE',
    'SOC_EXPIRATION_ISSUE_DATE',
    'EffectiveDate',
    'SaleExpirationDate',
    'INIT_ACTIVATION_DATE',
    'SUB_STATUS_DATE',
    'IXC_EFFECTIVE_DATE',
    'COMMIT_START_DATE',
    'COMMIT_END_DATE',
    'PAPER_WORK_DATE',
    'NEXT_CTN_CHG_DATE',
    'PRV_CTN_CHG_DATE',
    'NEXT_BAN_MOVE_DATE',
    'PRV_BAN_MOVE_DATE',
    'SUB_STS_ISSUE_DATE',
    'EARLIEST_ACTV_DATE',
    'LST_COM_ACTV_DATE',
    'SUB_MIG_DATE'
    }

def _looks_like_epoch(series: pd.Series) -> str | None:
    """Heuristic to decide if numeric values represent epoch seconds or milliseconds.
    Returns the unit string ('ms' or 's') or None if not epoch-like.
    """
    if series.empty:
        return None
    # Require at least one non-null numeric value
    vals = pd.to_numeric(series.dropna(), errors='coerce')
    vals = vals[vals.notna()]
    if vals.empty:
        return None
    # Large numbers (>1e11) are almost certainly milliseconds since epoch
    median_val = vals.median()
    if median_val > 1e11:  # ~ 1973 in ms threshold, safe for modern data
        return 'ms'
    if 1e9 < median_val < 1e11:  # seconds since epoch for contemporary dates
        return 's'
    return None

def normalize_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert epoch numeric date/time columns into human-readable strings.

    Safeguards added to avoid converting identifier columns (e.g. *_ID).
    Conversion now ONLY occurs when:
      - Column name contains one of DATE_COL_HINTS AND
      - Column name is not an excluded exact identifier AND
      - Column name does not simply end with '_ID' (unless it also contains 'DATE') AND
      - Numeric values look like epoch seconds/milliseconds.
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        name_upper = col.upper()
        if name_upper in EXCLUDE_EXACT:
            continue
        # Blocks plain *_ID columns unless they explicitly include DATE
        if name_upper.endswith('_ID') and 'DATE' not in name_upper:
            continue
        ser = out[col]
        if ser.dropna().empty or not pd.api.types.is_numeric_dtype(ser):
            continue
        # Require a name hint; this prevents converting generic numeric IDs
        name_has_hint = any(h in name_upper for h in DATE_COL_HINTS)
        if not name_has_hint and name_upper not in FORCE_DATETIME_COLUMNS:
            continue
        unit = _looks_like_epoch(ser)
        if not unit:
            continue
        try:
            coerced = pd.to_numeric(ser, errors='coerce')
            dt = pd.to_datetime(coerced, unit=unit, utc=True).dt.tz_convert(None)
            has_time = any(x.hour != 0 or x.minute != 0 or x.second != 0 for x in dt.dropna())
            formatted = dt.dt.strftime('%Y-%m-%d %H:%M') if has_time else dt.dt.strftime('%Y-%m-%d')
            out[col] = formatted.where(~dt.isna(), other=pd.NA)
        except Exception:
            continue
    return out

def run_eip_lookup(eip_id: str):
    eip_id = (eip_id or '').strip()
    if not eip_id or eip_id.lower() == 'none':
        session['eip_id'] = ''
        return
    session['eip_id'] = eip_id
    # main data (primary then fallback)
    primary = get_main_data_primary(eip_id)
    use_fallback = primary.empty or 'BAN' not in primary.columns or primary['BAN'].dropna().empty
    if use_fallback:
        main_df = get_main_data_fallback(eip_id)
        session['main_fallback_used'] = True
    else:
        main_df = primary
        session['main_fallback_used'] = False
    session['df_main'] = _encode_df(main_df)

    # promo errors
    errors_df = get_promo_error_reasons(eip_id)
    session['promo_errors'] = _encode_df(errors_df)

    # order detail IDs (with fallback query)
    order_ids: List[str] = []
    if not main_df.empty and 'ORDER_DETAIL_ID' in main_df.columns:
        order_ids = [str(x) for x in main_df['ORDER_DETAIL_ID'].dropna().unique() if str(x).strip()]
    if not order_ids:
        od_df = get_order_detail_ids(eip_id)
        if not od_df.empty and 'ORDER_DETAIL_ID' in od_df.columns:
            order_ids = [str(x) for x in od_df['ORDER_DETAIL_ID'].dropna().unique() if str(x).strip()]
    session['order_ids'] = order_ids
    session['missing_order_ids'] = len(order_ids) == 0

    # derive BAN
    used_ban = ''
    if not main_df.empty and 'BAN' in main_df.columns and not main_df['BAN'].dropna().empty:
        used_ban = str(main_df['BAN'].dropna().iloc[0])
    session['used_ban'] = used_ban
    session['missing_ban'] = used_ban == ''

    # rate plan + AAL lines if BAN present
    if used_ban:
        rate_df = get_rate_plan_data(used_ban)
        if not rate_df.empty:
            rate_df = deduplicate_columns(rate_df)
        session['rate_plans'] = _encode_df(rate_df)
        aal_df = get_active_aal_lines(used_ban)
        session['aal_lines'] = _encode_df(aal_df)

    # trade data
    trade_df = get_trade_data_qr(order_ids)
    session['trade_data'] = _encode_df(trade_df)
    session['trade_query_attempted'] = True

def run_ban_to_eip_list(ban: str):
    ban = (ban or '').strip()
    if not ban:
        return
    eip_list_df = get_eip_ids_by_ban(ban)
    session['eip_list'] = _encode_df(eip_list_df)
    session['eip_list_attempted'] = True

def run_ban_to_eip_list_for_mode(ban: str):
    run_ban_to_eip_list(ban)

def run_selected_eip(eip_id: str):
    run_eip_lookup(eip_id)

def process_chat(prompt: str):
    prompt = prompt or ''
    promo_code = extract_promo_code(prompt)
    elig_df = get_promo_eligibility_context(promo_code) if promo_code else pd.DataFrame()
    if not elig_df.empty:
        elig_df = deduplicate_columns(elig_df)

    reply = ""

    # Try LLM-powered response first
    try:
        from ai.client import is_ai_available
        if is_ai_available():
            from ai.chat import pete_chat_completion
            from ai.tools import build_pete_handlers
            import research.services as research_svc
            from factory import data_manager

            # Build session context from current PETE state
            session_data = {
                'eip_id': session.get('eip_id', ''),
                'used_ban': session.get('used_ban', ''),
                'promo_code': promo_code or '',
            }
            if not elig_df.empty:
                session_data['eligibility_summary'] = elig_df.head(50).to_string(index=False)
            errors_raw = session.get('promo_errors')
            if errors_raw:
                err_df = _decode_df(errors_raw)
                if not err_df.empty:
                    session_data['error_summary'] = err_df.head(20).to_string(index=False)
            main_raw = session.get('df_main')
            if main_raw:
                main_df = _decode_df(main_raw)
                if not main_df.empty:
                    session_data['main_data_summary'] = main_df.head(10).to_string(index=False)

            handlers = build_pete_handlers(data_manager, research_svc)
            history = session.get('chat_history', [])
            reply = pete_chat_completion(prompt, history, session_data, handlers)
            if reply.startswith("AI error:"):
                import logging
                logging.getLogger(__name__).warning("[PETE] LLM error, falling back: %s", reply)
                reply = ""
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("[PETE] LLM chat failed, falling back to keywords: %s", e)
        reply = ""

    # Fallback to keyword matching if LLM returned nothing
    if not reply:
        reply = generate_pete_response(prompt, elig_df if not elig_df.empty else None)

    history = session.get('chat_history', [])
    history.append({'role': 'user', 'content': prompt})
    history.append({'role': 'assistant', 'content': reply})
    session['chat_history'] = history
    return promo_code, reply

def serialize_df(df: Any):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    # Uniform borderless HTML table for PETE UI; use shared .pete-table styling
    return df.to_html(classes='pete-table', index=False, border=0)

def gather_template_context() -> Dict:
    df_main = normalize_datetime_columns(_decode_df(session.get('df_main')))
    promo_errors = normalize_datetime_columns(_decode_df(session.get('promo_errors')))
    rate_plans = normalize_datetime_columns(_decode_df(session.get('rate_plans')))
    aal_lines = normalize_datetime_columns(_decode_df(session.get('aal_lines')))
    trade_data = normalize_datetime_columns(_decode_df(session.get('trade_data')))
    eip_list = _decode_df(session.get('eip_list'))
    eip_ids: List[str] = []
    if not eip_list.empty and 'EQUIP_ID' in eip_list.columns:
        eip_ids = [str(x) for x in eip_list['EQUIP_ID'].dropna().unique() if str(x).strip()]
    return {
        'chat_history': session.get('chat_history', []),
        'eip_id': session.get('eip_id', ''),
        'used_ban': session.get('used_ban', ''),
        'order_ids': session.get('order_ids', []),
        'trade_query_attempted': session.get('trade_query_attempted', False),
        'last_mode': session.get('last_mode', ''),
        'last_ban': session.get('last_ban', ''),
        'eip_list_attempted': session.get('eip_list_attempted', False),
        'main_fallback_used': session.get('main_fallback_used', False),
        'missing_ban': session.get('missing_ban', False),
        'missing_order_ids': session.get('missing_order_ids', False),
    'eip_df_html': eip_list.to_html(classes='pete-table', index=False, border=0) if not eip_list.empty else None,
        'eip_ids': eip_ids,
        'df_html': serialize_df(df_main),
        'error_df_html': serialize_df(promo_errors),
        'rate_plan_df_html': serialize_df(rate_plans),
        'aal_df_html': serialize_df(aal_lines),
        'trade_df_html': serialize_df(trade_data),
    }
