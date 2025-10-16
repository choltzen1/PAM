"""Central authoritative mapping between canonical (UI/API) field names and
physical database column names for the PAM promotions table.

The goal: single source of truth so that adding a new editable field only
requires modifying this file (not scattered lists in storage / database layers).
"""
from typing import Dict, Set

# Canonical -> physical column name mapping. Keys are the names used throughout
# the application (forms, JSON, API). Values are the exact column names in SQL Server.
FIELD_DB_MAP: Dict[str, str] = {
    # Identity / descriptive
    'bill_facing_name': 'bill facing name',
    'initiative_name': 'initiative_name',
    'description': 'description',
    'promo_notes': 'promo_notes',
    'Owner': 'Owner',
    'orbit_id': 'orbit_id',
    'orbit_link': 'orbit_link',
    'legal_link': 'legal_link',
    'c2_link': 'c2_link',
    # Pricing / offer terms
    'discount': 'discount',
    'amount': 'amount',
    'nseip_drop': 'nseip_drop',
    'dcd_web_cart': 'dcd_web_cart',
    'product_type': 'product_type',
    'bogo': 'bogo',
    'fpd_display_promo': 'fpd_display_promo',
    'on_menu': 'on_menu',
    # Dates / timing
    'promo_start_date': 'promo_start_date',
    'promo_end_date': 'promo_end_date',
    'comm_end_date': 'comm_end_date',
    'promo_duration': 'promo_duration',
    'delay_time': 'delay_time',
    'application_grace_period': 'application_grace_period',
    'promo_grace': 'promo_grace',
    'trade_in_grace': 'trade_in_grace',
    # Execution & eligibility
    'device_sales_type': 'device_sales_type',
    'activation_type': 'activation_type',
    'active_line_required': 'active_line_required',
    'maintain_soc': 'maintain_soc',
    'maintain_active_line': 'maintain_active_line',
    'crffc_maintainactivelinedev': 'crffc_maintainactivelinedev',
    'limit_per_ban': 'limit_per_ban',
    'min_gsm_count': 'min_gsm_count',
    'max_gsm_count': 'max_gsm_count',
    'port_in_group_id': 'port_in_group_id',
    'trade_in_group_id': 'trade_in_group_id',
    'bolt_trade_in_grp_id': 'bolt_trade_in_grp_id',
    'flow_ind': 'flow_ind',
    'bptcr': 'bptcr',
    'mpss_lookback': 'mpss_lookback',
    # Segmentation
    'segment_name': 'segment_name',
    'sub_segment': 'sub_segment',
    'segment_group_id': 'segment_group_id',
    'segment_level': 'segment_level',
    # Groupings / classification
    'market_group': 'market_group',
    'store_group': 'store_group',
    'soc_grouping': 'soc_grouping',
    'account_type': 'account_type',
    'sales_application': 'sales_application',
    'sku_group_id': 'sku_group_id',
    'device_status_group_id': 'device_status_group_id',
    'clawback_indicator': 'clawback_indicator',
    # Trade tiers (make/model groups)
    'mk_mdl_grp_tier_1': 'mk_mdl_grp_tier_1',
    'mk_mdl_grp_tier_1_amount': 'mk_mdl_grp_tier_1_amount',
    'mk_mdl_grp_tier_1_condition_id': 'mk_mdl_grp_tier_1_condition_id',
    'mk_mdl_grp_tier_1_min_fmv': 'mk_mdl_grp_tier_1_min_fmv',
    'mk_mdl_grp_tier_1_max_fmv': 'mk_mdl_grp_tier_1_max_fmv',
    'mk_mdl_grp_tier_2': 'mk_mdl_grp_tier_2',
    'mk_mdl_grp_tier_2_amount': 'mk_mdl_grp_tier_2_amount',
    'mk_mdl_grp_tier_2_condition_id': 'mk_mdl_grp_tier_2_condition_id',
    'mk_mdl_grp_tier_2_min_fmv': 'mk_mdl_grp_tier_2_min_fmv',
    'mk_mdl_grp_tier_2_max_fmv': 'mk_mdl_grp_tier_2_max_fmv',
    'mk_mdl_grp_tier_3': 'mk_mdl_grp_tier_3',
    'mk_mdl_grp_tier_3_amount': 'mk_mdl_grp_tier_3_amount',
    'mk_mdl_grp_tier_3_condition_id': 'mk_mdl_grp_tier_3_condition_id',
    'mk_mdl_grp_tier_3_min_fmv': 'mk_mdl_grp_tier_3_min_fmv',
    'mk_mdl_grp_tier_3_max_fmv': 'mk_mdl_grp_tier_3_max_fmv',
    'mk_mdl_grp_tier_4': 'mk_mdl_grp_tier_4',
    'mk_mdl_grp_tier_4_amount': 'mk_mdl_grp_tier_4_amount',
    'mk_mdl_grp_tier_4_condition_id': 'mk_mdl_grp_tier_4_condition_id',
    'mk_mdl_grp_tier_4_min_fmv': 'mk_mdl_grp_tier_4_min_fmv',
    'mk_mdl_grp_tier_4_max_fmv': 'mk_mdl_grp_tier_4_max_fmv',
    # Promo tiered amounts/devices
    'tiered_grp_id': 'tiered_grp_id',
    'promo_tier_1_amount': 'promo_tier_1_amount',
    'promo_tier_1_sku_group_id': 'promo_tier_1_sku_group_id',
    'promo_tier_1_devices': 'promo_tier_1_devices',
    'promo_tier_2_amount': 'promo_tier_2_amount',
    'promo_tier_2_sku_group_id': 'promo_tier_2_sku_group_id',
    'promo_tier_2_devices': 'promo_tier_2_devices',
    'promo_tier_3_amount': 'promo_tier_3_amount',
    'promo_tier_3_sku_group_id': 'promo_tier_3_sku_group_id',
    'promo_tier_3_devices': 'promo_tier_3_devices',
    # Links
    'sku_link': 'sku_link',
    'tradein_link': 'tradein_link',
    # Misc / status
    'Broken_Trade': 'Broken_Trade',
    'Anticipated_volume_take_rates_total': 'Anticipated_volume_take_rates_total',
    'Status': 'Status',
    'crffc_eligibletradeindevices': 'crffc_eligibletradeindevices',
    'cat_lobchannelhorizontalname': 'cat_lobchannelhorizontalname',
    'cat_additionaleligibilityrequirementsname': 'cat_additionaleligibilityrequirementsname',
    'cat_eligibledevices': 'cat_eligibledevices',
    'cat_channelsname': 'cat_channelsname',
    'cat_description': 'cat_description',
    'dcd_jira': 'dcd_jira',
}

# Fields that are surfaced but not editable (primary keys, immutable orbit metadata, etc.)
READ_ONLY_FIELDS: Set[str] = {'code', 'orbit_id'}

# Convenience derived sets
CANONICAL_FIELDS: Set[str] = set(FIELD_DB_MAP.keys())
EDITABLE_CANONICAL_FIELDS: Set[str] = {f for f in CANONICAL_FIELDS if f not in READ_ONLY_FIELDS}

def canonical_to_physical(canonical: str) -> str:
    """Return the physical DB column for a canonical field name (or the name itself if unmapped)."""
    return FIELD_DB_MAP.get(canonical, canonical)

def needs_brackets(physical: str) -> bool:
    """Determine if a physical column name needs SQL Server bracket quoting."""
    # Quote if contains space or any char outside safe [A-Za-z0-9_]
    import re
    return bool(re.search(r"[^A-Za-z0-9_]", physical))

def quote_identifier(physical: str) -> str:
    if physical.startswith('[') and physical.endswith(']'):
        return physical
    return f'[{physical}]' if needs_brackets(physical) else physical
