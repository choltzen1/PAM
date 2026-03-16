import re
from io import BytesIO

import pandas as pd
from flask import Blueprint, jsonify, render_template, request, send_file

from auth import role_required
from data.database import DatabaseManager

lists_bp = Blueprint('lists', __name__, url_prefix='/lists')

TRADE_CATALOG_TABLE = 'PAM.Trade_Catalog_Assurant'


def _normalize_name(name: str) -> str:
    """Insert a space between 2+ consecutive letters and an immediately following digit.

    This handles catalog inconsistencies like 'Flip3' vs 'Flip 3' and 'Fold5' vs 'Fold 5'
    without affecting single-letter model codes like 'S20', 'A32', or '5G'.

    Examples:
        'Galaxy Z Flip3 5G'  → 'Galaxy Z Flip 3 5G'
        'Galaxy Z Fold2 5G'  → 'Galaxy Z Fold 2 5G'  (searched alongside original)
        'Galaxy S20'         → 'Galaxy S20'           (unchanged — 'S' is one letter)
        'iPhone 13'          → 'iPhone 13'            (unchanged — space already there)
    """
    return re.sub(r'([A-Za-z]{2,})(\d)', r'\1 \2', name)


@lists_bp.route('/')
@role_required('pam_users')
def index():
    return render_template('lists/lists_home.html')


@lists_bp.route('/sku')
@role_required('pam_users')
def sku_lists():
    return render_template('lists/sku_lists.html')


@lists_bp.route('/tradein')
@role_required('pam_users')
def tradein_lists():
    return render_template('lists/tradein_lists.html')


def _get_known_brands(db: DatabaseManager) -> dict:
    """Return lowercase→canonical mapping of all MAXVALUE_MFG values in the catalog."""
    df = db.get_dataframe(
        f'SELECT DISTINCT MAXVALUE_MFG FROM {TRADE_CATALOG_TABLE} WHERE MAXVALUE_MFG IS NOT NULL'
    )
    return {m.strip().lower(): m.strip() for m in df['MAXVALUE_MFG'].dropna().tolist()}


def _parse_tier(raw: str, known_brands: dict) -> list:
    """Parse a tier textarea into (brand, device_name) pairs.

    Lines whose stripped text matches a known MAXVALUE_MFG are treated as brand
    headers — they set the brand context for subsequent lines but are not searched.
    """
    entries = []
    current_brand = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower() in known_brands:
            current_brand = known_brands[line.lower()]
        else:
            entries.append((current_brand, line))
    return entries


@lists_bp.route('/tradein/generate', methods=['POST'])
@role_required('pam_users')
def tradein_generate():
    data = request.get_json(silent=True) or {}

    db = DatabaseManager()

    try:
        known_brands = _get_known_brands(db)
    except Exception as e:
        return jsonify({'error': f'Failed to load catalog brands: {e}'}), 500

    tier1_entries = _parse_tier(data.get('tier1', ''), known_brands)
    tier2_entries = _parse_tier(data.get('tier2', ''), known_brands)
    tier3_entries = _parse_tier(data.get('tier3', ''), known_brands)

    if not tier1_entries and not tier2_entries and not tier3_entries:
        return jsonify({'error': 'All tier boxes are empty. Please enter at least one device.'}), 400

    # Map device name → (tier, brand); first occurrence wins
    device_info = {}
    for tier_num, entries in ((1, tier1_entries), (2, tier2_entries), (3, tier3_entries)):
        for brand, device in entries:
            device_info.setdefault(device, (tier_num, brand))

    all_devices = list(device_info.keys())
    frames = []

    for device in all_devices:
        tier_num, brand = device_info[device]
        device_norm = _normalize_name(device)

        # Build match clause: search both original and normalized forms so that
        # e.g. "Flip3" finds "Flip 3" in the catalog, and "Fold2" still finds "Fold2".
        params: dict = {'exact': device, 'prefix': f'{device} %'}
        if device_norm != device:
            params['exact_norm'] = device_norm
            params['prefix_norm'] = f'{device_norm} %'
            match_clause = (
                '(MARKETING_NAME = :exact'
                ' OR MARKETING_NAME = :exact_norm'
                ' OR MARKETING_NAME LIKE :prefix'
                ' OR MARKETING_NAME LIKE :prefix_norm)'
            )
        else:
            match_clause = '(MARKETING_NAME = :exact OR MARKETING_NAME LIKE :prefix)'

        where_parts = [match_clause]

        # Filter by manufacturer to prevent cross-brand results
        if brand:
            params['brand'] = brand
            where_parts.append('MAXVALUE_MFG = :brand')

        # Detect children using normalized names so "Flip3" is correctly identified
        # as a child of "Galaxy Z Flip" (normalized "Flip 3" starts with "Flip ")
        children = [
            d for d in all_devices
            if d != device
            and _normalize_name(d).lower().startswith(device_norm.lower() + ' ')
        ]

        # Exclude children using the original, normalized, AND a family-prefix pattern.
        # The family prefix blocks all siblings in a numbered generation:
        #   child "Galaxy Z Flip 7 5G" → also add NOT LIKE 'Galaxy Z Flip 7 %'
        #   so "Galaxy Z Flip 7 FE 5G" is excluded even though it doesn't start
        #   with "Galaxy Z Flip 7 5G".
        # The trailing space before % is intentional: it prevents "Galaxy Z Flip 5 %"
        # from accidentally excluding "Galaxy Z Flip 5G" (the original 5G edition).
        for i, child in enumerate(children):
            child_norm = _normalize_name(child)

            # Family prefix = parent + " " + first token after parent in child
            suffix_tokens = child_norm[len(device_norm):].strip().split()
            family_prefix = f'{device_norm} {suffix_tokens[0]}' if suffix_tokens else None

            patterns = list(dict.fromkeys(filter(None, [
                f'{child}%',                                         # original input form
                f'{child_norm}%',                                    # normalized form
                f'{family_prefix} %' if family_prefix else None,     # whole generation family
            ])))

            for j, pattern in enumerate(patterns):
                key = f'excl{i}_{j}'
                params[key] = pattern
                where_parts.append(f'MARKETING_NAME NOT LIKE :{key}')

        # If any input child represents a numbered generation (e.g. "iPhone SE 2", "iPhone SE 3"),
        # also exclude catalog entries with a numeric suffix not explicitly in the input
        # (prevents e.g. "iPhone SE 4" from leaking through as a variant of "iPhone SE").
        if any(_normalize_name(c).split()[-1].isdigit() for c in children):
            params['excl_numgen'] = f'{device_norm} [0-9]%'
            where_parts.append('MARKETING_NAME NOT LIKE :excl_numgen')

        sql = (
            f'SELECT * FROM {TRADE_CATALOG_TABLE} WITH (NOLOCK) '
            f'WHERE {" AND ".join(where_parts)}'
        )

        try:
            df = db.get_dataframe(sql, params)
        except Exception as e:
            return jsonify({'error': f'Database error while looking up "{device}": {e}'}), 500

        # Fallback 1 — strip brand prefix from the search term.
        # Handles cases like "OnePlus 10 Pro 5G" where the catalog stores just "10 Pro 5G"
        # under MAXVALUE_MFG = 'OnePlus'.
        if df.empty and brand:
            stripped = device_norm
            if stripped.lower().startswith(brand.lower() + ' '):
                stripped = stripped[len(brand):].strip()
            if stripped and stripped != device_norm:
                fb1_params = {'exact': stripped, 'prefix': f'{stripped} %', 'brand': brand}
                fb1_sql = (
                    f'SELECT * FROM {TRADE_CATALOG_TABLE} WITH (NOLOCK) '
                    f'WHERE (MARKETING_NAME = :exact OR MARKETING_NAME LIKE :prefix)'
                    f' AND MAXVALUE_MFG = :brand'
                )
                try:
                    df = db.get_dataframe(fb1_sql, fb1_params)
                except Exception:
                    df = pd.DataFrame()

        # Fallback 2 — keyword search within brand.
        # Handles devices whose catalog name shares no common prefix with the input
        # (e.g. Motorola devices whose marketing names differ entirely from the input).
        # All significant words from the input must appear somewhere in the catalog name.
        #
        # Contamination exclusion: any word that appears in a sibling input device
        # (same brand, different device) but NOT in the current search term is added
        # as a NOT LIKE clause. This dynamically prevents cross-model pollution without
        # a hardcoded exclusion list — e.g. when "edge 5G 2022/2023/2024" and
        # "razr 40 5G" are both in the input, searching "razr 40 5G" automatically
        # excludes 'edge' because it belongs to a sibling device.
        # Connectivity terms (5g, 4g, etc.) are excluded from contamination detection
        # since they appear across many models and are already enforced as keywords.
        if df.empty and brand:
            _SKIP = {'4g', 'lte', 'wifi', brand.lower()}
            raw_words = re.sub(r'\+', ' plus ', device_norm.lower()).split()
            keywords = [w for w in raw_words if w not in _SKIP and len(w) > 1]
            if keywords:
                fb2_params = {'brand': brand}
                fb2_parts = ['MAXVALUE_MFG = :brand']
                for k, word in enumerate(keywords):
                    fb2_params[f'kw{k}'] = f'%{word}%'
                    fb2_parts.append(f'MARKETING_NAME LIKE :kw{k}')

                # Derive contaminant words from sibling devices in the same brand.
                _CONTAM_SKIP = {'4g', '5g', 'lte', 'wifi', brand.lower()}
                sibling_words: set[str] = set()
                for other_dev, (_, other_brand) in device_info.items():
                    if other_dev != device and other_brand and other_brand.lower() == brand.lower():
                        other_raw = re.sub(r'\+', ' plus ', _normalize_name(other_dev).lower()).split()
                        sibling_words.update(
                            w for w in other_raw if w not in _CONTAM_SKIP and len(w) > 1
                        )
                kw_protected = {w for w in keywords if w not in _CONTAM_SKIP}
                contaminants = sibling_words - kw_protected
                for k, word in enumerate(contaminants):
                    fb2_params[f'cexcl{k}'] = f'%{word}%'
                    fb2_parts.append(f'MARKETING_NAME NOT LIKE :cexcl{k}')

                fb2_sql = (
                    f'SELECT * FROM {TRADE_CATALOG_TABLE} WITH (NOLOCK) '
                    f'WHERE {" AND ".join(fb2_parts)}'
                )
                try:
                    df = db.get_dataframe(fb2_sql, fb2_params)
                except Exception:
                    df = pd.DataFrame()

        if df.empty:
            continue

        df['Tiers'] = tier_num
        frames.append(df)

    if not frames:
        return jsonify({'error': 'No matching devices found in the catalog for the provided input.'}), 404

    result = pd.concat(frames, ignore_index=True)
    id_cols = [c for c in result.columns if c in ('MAXVALUE_MFG', 'MARKETING_NAME')]
    if len(id_cols) == 2:
        result = result.sort_values('Tiers').drop_duplicates(subset=id_cols, keep='first')
    else:
        result = result.drop_duplicates()

    # Strip demo/dummy catalog entries
    if 'MARKETING_NAME' in result.columns:
        result = result[~result['MARKETING_NAME'].str.contains(r'(?i)\bDemo\b|\bDummy\b', regex=True, na=False)]

    # Column order: MAXVALUE_MFG, MARKETING_NAME, Tiers, then any remaining catalog columns
    priority = ['MAXVALUE_MFG', 'MARKETING_NAME', 'Tiers']
    remaining = [c for c in result.columns if c not in priority]
    result = result[[c for c in priority if c in result.columns] + remaining]

    buf = BytesIO()
    result.to_excel(buf, index=False, engine='openpyxl')
    buf.seek(0)

    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='trade_list.xlsx',
    )
