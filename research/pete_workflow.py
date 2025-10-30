"""Simplified PETE workflow recreation.

Responsibilities:
 - Maintain session state for EIP promo data, derived BAN, ancillary datasets.
 - Provide BAN-based EIP discovery list.
 - Execute primary + fallback main data queries (via services module).
 - Persist chat history and generate responses using promo eligibility subset.
"""

from typing import Dict, List, Any
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

def _encode_df(df: pd.DataFrame | None) -> str | None:
    if df is None or df.empty:
        return None
    return df.to_json(orient="split")

def _decode_df(raw: Any) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame()
    try:
        return pd.read_json(raw, orient="split")
    except Exception:
        return pd.DataFrame()

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
    reply = generate_pete_response(prompt, elig_df if not elig_df.empty else None)
    history = session.get('chat_history', [])
    history.append({'role': 'user', 'content': prompt})
    history.append({'role': 'assistant', 'content': reply})
    session['chat_history'] = history
    return promo_code, reply

def serialize_df(df: Any):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    return df.to_html(classes='table table-sm table-striped', index=False)

def gather_template_context() -> Dict:
    df_main = _decode_df(session.get('df_main'))
    promo_errors = _decode_df(session.get('promo_errors'))
    rate_plans = _decode_df(session.get('rate_plans'))
    aal_lines = _decode_df(session.get('aal_lines'))
    trade_data = _decode_df(session.get('trade_data'))
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
        'eip_df_html': eip_list.to_html(classes='table table-sm table-striped', index=False) if not eip_list.empty else None,
        'eip_ids': eip_ids,
        'df_html': serialize_df(df_main),
        'error_df_html': serialize_df(promo_errors),
        'rate_plan_df_html': serialize_df(rate_plans),
        'aal_df_html': serialize_df(aal_lines),
        'trade_df_html': serialize_df(trade_data),
    }
