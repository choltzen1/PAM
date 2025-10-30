"""Workflow orchestration for PETE page (legacy form-based flow) within research workspace.
Uses existing service functions for data retrieval, providing higher-level bundles.
"""
from typing import Dict, List, Any
import pandas as pd
from flask import session
from .services import (
    get_main_data,
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
    "used_ban", "eip_id", "order_ids", "trade_query_attempted", "chat_history"
]

def ensure_session_defaults():
    for k in SESSION_KEYS:
        session.setdefault(k, None if k not in ("chat_history", "order_ids") else ([] if k in ("chat_history", "order_ids") else None))
    session.setdefault("used_ban", "")
    session.setdefault("trade_query_attempted", False)

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
    eip_id = (eip_id or "").strip()
    session["eip_id"] = eip_id
    if not eip_id:
        return
    main_df = get_main_data(eip_id)
    session["df_main"] = _encode_df(main_df)
    errors_df = get_promo_error_reasons(eip_id)
    session["promo_errors"] = _encode_df(errors_df)
    order_ids: List[str] = []
    if not main_df.empty and "ORDER_DETAIL_ID" in main_df.columns:
        order_ids = [str(x) for x in main_df["ORDER_DETAIL_ID"].dropna().unique()]
    # Fallback: try separate ORDER_DETAIL_ID fetch if missing
    if not order_ids:
        od_df = get_order_detail_ids(eip_id)
        if not od_df.empty and "ORDER_DETAIL_ID" in od_df.columns:
            order_ids = [str(x) for x in od_df["ORDER_DETAIL_ID"].dropna().unique()]
    session["order_ids"] = order_ids
    # derive BAN
    used_ban = ""
    if not main_df.empty and "BAN" in main_df.columns and not main_df["BAN"].dropna().empty:
        used_ban = str(main_df["BAN"].dropna().iloc[0])
    session["used_ban"] = used_ban
    if used_ban:
        rate_df = get_rate_plan_data(used_ban)
        if not rate_df.empty:
            rate_df = deduplicate_columns(rate_df)
        session["rate_plans"] = _encode_df(rate_df)
        aal_df = get_active_aal_lines(used_ban)
        session["aal_lines"] = _encode_df(aal_df)
    trade_df = get_trade_data_qr(order_ids)
    session["trade_data"] = _encode_df(trade_df)
    session["trade_query_attempted"] = True

def run_ban_to_eip_list(ban: str):
    ban = (ban or "").strip()
    if not ban:
        return
    eip_list_df = get_eip_ids_by_ban(ban)
    session["eip_list"] = _encode_df(eip_list_df)

def run_selected_eip(eip_id: str):
    run_eip_lookup(eip_id)

def process_chat(prompt: str):
    promo_code = extract_promo_code(prompt or "")
    elig_df = get_promo_eligibility_context(promo_code) if promo_code else pd.DataFrame()
    if not elig_df.empty:
        elig_df = deduplicate_columns(elig_df)
    reply = generate_pete_response(prompt, elig_df if not elig_df.empty else None)
    history = session.get("chat_history", [])
    history.append({"role":"user", "content":prompt})
    history.append({"role":"assistant", "content":reply})
    session["chat_history"] = history
    return promo_code, reply

def serialize_df(df: Any):
    if df is None:
        return None
    if isinstance(df, pd.DataFrame):
        if df.empty:
            return None
        return df.to_html(classes="table table-sm table-striped", index=False)
    return None

def gather_template_context() -> Dict:
    # decode needed DataFrames for HTML rendering
    df_main = _decode_df(session.get("df_main"))
    promo_errors = _decode_df(session.get("promo_errors"))
    rate_plans = _decode_df(session.get("rate_plans"))
    aal_lines = _decode_df(session.get("aal_lines"))
    trade_data = _decode_df(session.get("trade_data"))
    eip_list = _decode_df(session.get("eip_list"))
    return {
        "chat_history": session.get("chat_history", []),
        "eip_id": session.get("eip_id", ""),
        "used_ban": session.get("used_ban", ""),
        "order_ids": session.get("order_ids", []),
        "trade_query_attempted": session.get("trade_query_attempted", False),
        "eip_df": eip_list if not eip_list.empty else None,
        "df_html": serialize_df(df_main),
        "error_df_html": serialize_df(promo_errors),
        "rate_plan_df_html": serialize_df(rate_plans),
        "aal_df_html": serialize_df(aal_lines),
        "trade_df_html": serialize_df(trade_data),
    }
