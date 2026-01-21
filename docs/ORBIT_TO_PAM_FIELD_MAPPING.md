# ORBIT → PAM Field Mapping Reference

> **Last Updated**: January 21, 2026  
> **Source**: `dbo.ORBIT_Reporting_Table` (Microsoft Fabric)  
> **Destination**: PAM PromoQuality Database

---

## Quick Reference: ORBIT Column → PAM Field

| PAM Field | ORBIT Source Column | Fallback Column | Notes |
|-----------|---------------------|-----------------|-------|
| **IDENTITY / DESCRIPTIVE** | | | |
| `bill_facing_name` | `cat_billname` | - | Customer-facing bill name |
| `initiative_name` | `cat_initiativename` | - | Promo initiative name |
| `description` | `cat_description` | - | Full description text |
| `promo_notes` | `cat_notes` | - | Additional notes |
| `Owner` | `crffc_productownername` | `crffc_businessownername` | Product owner preferred |
| `business_owner` | `crffc_businessownername` | - | Business owner only |
| `product_owner` | `crffc_productownername` | - | Product owner only |
| `sponsoring_vp` | `crffc_sponsoringvpname` | - | VP sponsor |
| `orbit_id` | `cat_gtmentryid` | `cat_legacygtmentryid` | GUID preferred, legacy backup |
| **DATES** | | | |
| `promo_start_date` | `cat_startdate` | `cat_requestedlaunchdate` | Actual start preferred |
| `promo_end_date` | `cat_enddate` | - | Promotion end |
| `comm_end_date` | `cat_commenddate` | - | Communication end |
| **PRICING / OFFER TERMS** | | | |
| `discount` | `cat_discount` | - | Discount value |
| `amount` | `cat_amount` | `crffc_amount` | Dollar amount |
| `nseip_drop` | `cat_nseipdrop` | - | NSEIP drop indicator |
| `dcd_web_cart` | `cat_dcdwebcart` | - | DCD web cart indicator |
| `product_type` | `cat_producttypename` | - | Product classification |
| `bogo` | `cat_bogo` | - | Buy One Get One |
| `fpd_display_promo` | `cat_fpddisplaypromo` | - | FPD display promo |
| `on_menu` | `cat_onmenu` | - | On menu indicator |
| **EXECUTION & ELIGIBILITY** | | | |
| `device_sales_type` | `cat_devicesalestypename` | - | Sale type |
| `activation_type` | `cat_activationtypename` | - | Activation type |
| `active_line_required` | `cat_activelinerequired` | - | Active line req |
| `maintain_soc` | `cat_maintainsoc` | - | Maintain SOC |
| `maintain_active_line` | `crffc_maintainactivelinedev` | - | Maintain active line |
| `limit_per_ban` | `cat_limitperban` | - | Per-BAN limit |
| `application_grace_period` | `cat_applicationgraceperiod` | - | Grace period |
| `trade_in_grace` | `cat_tradeingraceperiod` | - | Trade-in grace |
| **GROUPINGS / SEGMENTATION** | | | |
| `market_group` | `cat_marketgroupname` | - | Market group |
| `store_group` | `cat_storegroupname` | - | Store group |
| `soc_grouping` | `cat_socgrouping` | - | SOC group |
| `account_type` | `cat_accounttypename` | - | Account type |
| `sales_application` | `cat_salesapplicationname` | - | Sales app |
| `device_status_group_id` | `cat_devicestatusgroupid` | - | Device status |
| `segment_name` | `cat_segmentname` | - | Customer segment |
| **LINKS** | | | |
| `orbit_link` | `cat_orbitlink` | - | ORBIT URL |
| `legal_link` | `cat_legallink` | - | Legal doc link |
| `c2_link` | `cat_c2link` | - | C2 link |
| **ADDITIONAL FABRIC FIELDS** | | | |
| `cat_lobchannelhorizontalname` | `cat_lobchannelhorizontalname` | - | LOB/Channel |
| `cat_additionaleligibilityrequirementsname` | `cat_additionaleligibilityrequirementsname` | - | Eligibility reqs |
| `cat_eligibledevices` | `cat_eligibledevices` | - | Eligible devices |
| `cat_channelsname` | `cat_channelsname` | - | Channels |
| `crffc_eligibletradeindevices` | `crffc_eligibletradeindevices` | - | Trade-in devices |

---

## ORBIT Column Naming Conventions

The ORBIT table uses two prefixes:

### `cat_` prefix (Category/Catalog fields)
These are the main promotion attribute fields:
- `cat_billname` - Bill facing name
- `cat_initiativename` - Initiative name  
- `cat_description` - Description
- `cat_startdate` - Start date
- `cat_enddate` - End date
- `cat_gtmentryid` - GTM Entry ID (GUID)
- `cat_legacygtmentryid` - Legacy numeric ID
- `cat_discount`, `cat_amount`, `cat_bogo`, etc.

### `crffc_` prefix (CRM/Finance fields)
These appear to be from a different source system:
- `crffc_promocodeid` - Promo code
- `crffc_productownername` - Product owner
- `crffc_businessownername` - Business owner
- `crffc_sponsoringvpname` - Sponsoring VP
- `crffc_amount` - Amount (alternate)
- `crffc_maintainactivelinedev` - Maintain active line

---

## Fields NOT Mapped from ORBIT (Manual Entry in PAM)

These PAM fields have **no ORBIT source** and must be entered manually:

### Trade Tiers (make/model groups)
- `mk_mdl_grp_tier_1` through `mk_mdl_grp_tier_4`
- `mk_mdl_grp_tier_X_amount`
- `mk_mdl_grp_tier_X_condition_id`
- `mk_mdl_grp_tier_X_min_fmv` / `max_fmv`

### Promo Tiers
- `promo_tier_1_amount`, `promo_tier_2_amount`, `promo_tier_3_amount`
- `promo_tier_X_sku_group_id`
- `promo_tier_X_devices`
- `tiered_grp_id`

### Segment Details
- `sub_segment`
- `segment_group_id`
- `segment_level`

### Technical IDs
- `port_in_group_id`
- `trade_in_group_id`
- `bolt_trade_in_grp_id`
- `sku_group_id`

### Execution Details
- `min_gsm_count`, `max_gsm_count`
- `flow_ind`
- `bptcr`
- `mpss_lookback`
- `promo_duration`
- `delay_time`
- `promo_grace`
- `clawback_indicator`

### Status/Misc
- `Status`
- `Broken_Trade`
- `Anticipated_volume_take_rates_total`
- `sku_link`
- `tradein_link`
- `dcd_jira`

---

## Code Reference

### Mapping happens in:
- **[data/orbit_database.py](../data/orbit_database.py)** - `get_orbit_record()` method transforms ORBIT → PAM format
- **[data/field_map.py](../data/field_map.py)** - `FIELD_DB_MAP` defines PAM canonical → physical column names

### Key transformation logic (orbit_database.py):
```python
mapped = {
    'Owner': result.get('crffc_productownername') or result.get('crffc_businessownername'),
    'orbit_id': result.get('cat_gtmentryid') or result.get('cat_legacygtmentryid'),
    'promo_start_date': result.get('cat_startdate') or result.get('cat_requestedlaunchdate'),
    'amount': result.get('cat_amount') or result.get('crffc_amount'),
    # ... direct mappings ...
    'bill_facing_name': result.get('cat_billname'),
    'initiative_name': result.get('cat_initiativename'),
    # etc.
}
```

---

## Verification Checklist

To verify mapping accuracy, run:
```bash
python scripts/analyze_orbit_fields.py
```

This will:
1. ✅ List ALL columns in ORBIT_Reporting_Table
2. ✅ Show % populated for each column
3. ✅ Sample values from each field
4. ✅ Compare against PAM requirements

---

## Known Ambiguous Fields (Resolved)

| PAM Field | Decision | Rationale |
|-----------|----------|-----------|
| `Owner` | Use `crffc_productownername` first, fall back to `crffc_businessownername` | Product owner is more specific |
| `orbit_id` | Use `cat_gtmentryid` first, fall back to `cat_legacygtmentryid` | GUID is preferred, legacy for old records |
| `promo_start_date` | Use `cat_startdate` first, fall back to `cat_requestedlaunchdate` | Actual start preferred over requested |
| `amount` | Use `cat_amount` first, fall back to `crffc_amount` | Category amount takes precedence |
