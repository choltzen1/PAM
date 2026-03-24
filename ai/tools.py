"""Tool definitions and handler factories for PeteBot LLM function calling."""

import logging
import pandas as pd
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAI function-calling tool schemas
# ---------------------------------------------------------------------------

PETE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_promo_eligibility",
            "description": "Get eligibility rules for a promo code including SKUs, SOCs, segments, carriers, trade-in devices, and dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "promo_code": {"type": "string", "description": "The promo code (e.g., R160, S045)"}
                },
                "required": ["promo_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_promo_details",
            "description": "Get full promotion details from PAM (owner, dates, account type, activation type, sales application, trade tiers, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "promo_code": {"type": "string", "description": "The promo code to look up"}
                },
                "required": ["promo_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_promo_error_reasons",
            "description": "Get promo enrollment error reasons for a specific EIP_ID. Useful for troubleshooting why a promo was not applied.",
            "parameters": {
                "type": "object",
                "properties": {
                    "eip_id": {"type": "string", "description": "10-digit Equipment Installment Plan ID"}
                },
                "required": ["eip_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_rate_plan_data",
            "description": "Get rate plan / SOC information for a BAN (billing account number).",
            "parameters": {
                "type": "object",
                "properties": {
                    "ban": {"type": "string", "description": "9-digit Billing Account Number"}
                },
                "required": ["ban"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_aal_lines",
            "description": "Get active subscriber lines (Add-a-Line) for a BAN.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ban": {"type": "string", "description": "9-digit Billing Account Number"}
                },
                "required": ["ban"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_promos",
            "description": "Search PAM promotions by text (matches promo code, owner, or bill facing name). Returns up to 10 results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "Text to search for"}
                },
                "required": ["search_term"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_promos",
            "description": "Compare two promotions side-by-side, highlighting differences in key fields.",
            "parameters": {
                "type": "object",
                "properties": {
                    "promo_code_a": {"type": "string", "description": "First promo code"},
                    "promo_code_b": {"type": "string", "description": "Second promo code"},
                },
                "required": ["promo_code_a", "promo_code_b"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _truncate_df(df: Optional[pd.DataFrame], max_rows: int = 50) -> str:
    """Convert DataFrame to concise text, truncating if too large."""
    if df is None or df.empty:
        return "No data found."
    if len(df) > max_rows:
        truncated = df.head(max_rows)
        return truncated.to_string(index=False) + f"\n... (showing {max_rows} of {len(df)} rows)"
    return df.to_string(index=False)


KEY_PROMO_FIELDS = [
    'code', 'bill_facing_name', 'description', 'owner', 'orbit_id',
    'promo_start_date', 'promo_end_date', 'account_type', 'activation_type',
    'product_type', 'device_sales_type', 'soc_grouping', 'market_group',
    'store_group', 'sales_application', 'bogo', 'Broken_Trade', 'amount',
    'discount', 'maintain_soc', 'maintain_active_line', 'limit_per_ban',
    'promo_duration', 'delay_time', 'application_grace_period',
    'mk_mdl_grp_tier_1', 'mk_mdl_grp_tier_1_amount',
    'mk_mdl_grp_tier_2', 'mk_mdl_grp_tier_2_amount',
    'mk_mdl_grp_tier_3', 'mk_mdl_grp_tier_3_amount',
    'mk_mdl_grp_tier_4', 'mk_mdl_grp_tier_4_amount',
]


def _format_promo_dict(d: Optional[Dict[str, Any]], fields: Optional[List[str]] = None) -> str:
    """Format a promo dict into readable text for the LLM."""
    if not d:
        return "Promo not found."
    use_fields = fields or KEY_PROMO_FIELDS
    lines = []
    for k in use_fields:
        v = d.get(k)
        if v is not None and str(v).strip():
            lines.append(f"  {k}: {v}")
    if not lines:
        # Fall back to showing all non-empty fields
        for k, v in d.items():
            if v is not None and str(v).strip():
                lines.append(f"  {k}: {v}")
    return "\n".join(lines[:60]) if lines else "No details available."


COMPARE_FIELDS = [
    'code', 'bill_facing_name', 'owner', 'promo_start_date', 'promo_end_date',
    'account_type', 'activation_type', 'product_type', 'device_sales_type',
    'soc_grouping', 'market_group', 'store_group', 'amount', 'discount',
    'maintain_soc', 'maintain_active_line', 'bogo', 'Broken_Trade',
    'limit_per_ban', 'promo_duration',
]

# ---------------------------------------------------------------------------
# Handler factories
# ---------------------------------------------------------------------------

def build_pete_handlers(data_manager, research_services) -> Dict[str, Callable]:
    """Build handler functions for PETE tools, bound to the active data_manager and research services.

    Args:
        data_manager: PromoDataManager instance (from factory.py)
        research_services: The research.services module
    """

    def get_promo_eligibility(promo_code: str) -> str:
        df = research_services.get_promo_eligibility_context(promo_code.upper())
        if df is None or df.empty:
            return f"No eligibility rules found for {promo_code}."
        df = research_services.deduplicate_columns(df)
        summary_parts = []
        for col in ['SKU', 'SOC', 'Segment_name', 'Carrier_name', 'MAKE', 'MODEL',
                     'DISPLAY_PROMO_START_DATE', 'DISPLAY_PROMO_END_DATE', 'PRODUCT_TYPE',
                     'LINE_ST_GROUP_ID']:
            if col in df.columns:
                uniq = [str(x) for x in df[col].dropna().unique() if str(x).strip()]
                if uniq:
                    display = ', '.join(uniq[:25])
                    suffix = f" ... (+{len(uniq) - 25} more)" if len(uniq) > 25 else ""
                    summary_parts.append(f"{col} ({len(uniq)}): {display}{suffix}")
        return "\n".join(summary_parts) if summary_parts else "Eligibility data found but no key fields populated."

    def get_promo_details(promo_code: str) -> str:
        promo = data_manager.get_promo(promo_code.upper())
        return _format_promo_dict(promo)

    def get_promo_error_reasons(eip_id: str) -> str:
        df = research_services.get_promo_error_reasons(eip_id)
        return _truncate_df(df, max_rows=30)

    def get_rate_plan_data(ban: str) -> str:
        df = research_services.get_rate_plan_data(ban)
        if df is not None and not df.empty:
            df = research_services.deduplicate_columns(df)
        return _truncate_df(df, max_rows=30)

    def get_active_aal_lines(ban: str) -> str:
        df = research_services.get_active_aal_lines(ban)
        return _truncate_df(df, max_rows=30)

    def search_promos(search_term: str) -> str:
        result = data_manager.get_paginated_promos(page=1, per_page=10, search=search_term)
        promos = result.get('promos', [])
        if not promos:
            return f"No promotions found matching '{search_term}'."
        lines = []
        for p in promos:
            lines.append(
                f"- {p.get('code', '?')}: {p.get('bill_facing_name', '')} "
                f"(Owner: {p.get('owner', '')}, Type: {p.get('Desired_Execution', '')})"
            )
        return f"Found {len(promos)} promos:\n" + "\n".join(lines)

    def compare_promos(promo_code_a: str, promo_code_b: str) -> str:
        a = data_manager.get_promo(promo_code_a.upper())
        b = data_manager.get_promo(promo_code_b.upper())
        if not a:
            return f"Promo {promo_code_a} not found."
        if not b:
            return f"Promo {promo_code_b} not found."
        lines = [f"{'Field':<30} {promo_code_a.upper():<30} {promo_code_b.upper():<30}"]
        lines.append("-" * 90)
        for f in COMPARE_FIELDS:
            va = str(a.get(f, '') or '')
            vb = str(b.get(f, '') or '')
            marker = "  <-- DIFFERENT" if va != vb else ""
            lines.append(f"{f:<30} {va:<30} {vb:<30}{marker}")
        return "\n".join(lines)

    return {
        'get_promo_eligibility': get_promo_eligibility,
        'get_promo_details': get_promo_details,
        'get_promo_error_reasons': get_promo_error_reasons,
        'get_rate_plan_data': get_rate_plan_data,
        'get_active_aal_lines': get_active_aal_lines,
        'search_promos': search_promos,
        'compare_promos': compare_promos,
    }
