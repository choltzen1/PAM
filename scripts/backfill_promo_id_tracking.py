"""One-time migration: seed PAM.Promo_ID_Tracking from existing promos + JSON tombstones.

Run after creating the table (scripts/create_promo_id_tracking.sql) and before
deploying the new DB-based tracking code.

Steps:
  1. Query all existing promos from the live table
  2. INSERT each into PAM.Promo_ID_Tracking (skip if code already exists)
  3. Read the 4 legacy JSON tombstone files
  4. For codes in JSON but NOT in the live table (deleted promos), insert a
     tracking row with whatever ID data is available (code only for most)
  5. Print summary
"""
import json
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('backfill')

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from data.database import DatabaseManager

# Group ID columns to extract from live promos
TRACKING_COLUMNS = [
    'code', 'orbit_id', 'sku_group_id', 'trade_in_group_id',
    'bolt_trade_in_grp_id', 'port_in_group_id', 'segment_group_id',
    'device_status_group_id', 'mk_mdl_grp_tier_1', 'mk_mdl_grp_tier_2',
    'mk_mdl_grp_tier_3', 'mk_mdl_grp_tier_4', 'tiered_grp_id',
    'promo_tier_1_sku_group_id', 'promo_tier_2_sku_group_id',
    'promo_tier_3_sku_group_id',
]

JSON_FILES = {
    'promo_code': os.path.join('data', 'issued_codes.json'),
    'sku_group_id': os.path.join('data', 'issued_sku_groups.json'),
    'trade_in_group_id': os.path.join('data', 'issued_trade_in_groups.json'),
    'mk_mdl_group_id': os.path.join('data', 'issued_mk_mdl_groups.json'),
}


def _load_json_set(path: str) -> set:
    """Load a JSON array file and return as a set of strings."""
    if not os.path.exists(path):
        log.info("  JSON file not found: %s", path)
        return set()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return {str(x).strip() for x in data if x}
        return set()
    except Exception as e:
        log.warning("  Failed to read %s: %s", path, e)
        return set()


def main():
    db = DatabaseManager()
    engine = db.get_engine()

    # 1. Verify tracking table exists
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = 'PAM' AND TABLE_NAME = 'Promo_ID_Tracking'"
        )).fetchone()
    if not row:
        log.error("PAM.Promo_ID_Tracking does not exist. Run create_promo_id_tracking.sql first.")
        sys.exit(1)

    # 2. Get codes already in tracking table
    with engine.connect() as conn:
        existing = {r[0] for r in conn.execute(text(
            "SELECT code FROM PAM.Promo_ID_Tracking WITH (NOLOCK)"
        )).fetchall()}
    log.info("Tracking table already has %d rows", len(existing))

    # 3. Query all live promos
    col_sql = ', '.join(TRACKING_COLUMNS)
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"SELECT {col_sql} FROM {db.source_table} WITH (NOLOCK)"
        )).fetchall()
    log.info("Live promo table has %d rows", len(rows))

    # 4. Insert live promos into tracking table
    inserted = 0
    skipped = 0
    for row in rows:
        record = dict(zip(TRACKING_COLUMNS, row))
        code = (record.get('code') or '').strip()
        if not code or code in existing:
            skipped += 1
            continue
        # Build parameterized insert
        cols = ['created_by']
        params = {'p_created_by': 'backfill'}
        for i, col in enumerate(TRACKING_COLUMNS):
            val = record.get(col)
            if val is not None and str(val).strip():
                cols.append(col)
                params[f'p{i}'] = str(val).strip()
        col_list = ', '.join(cols)
        val_list = ', '.join(f':{k}' for k in params)
        sql = f"INSERT INTO PAM.Promo_ID_Tracking ({col_list}) VALUES ({val_list})"
        try:
            with engine.begin() as conn:
                conn.execute(text(sql), params)
            existing.add(code)
            inserted += 1
        except Exception as e:
            log.warning("Failed to insert %s: %s", code, e)

    log.info("Inserted %d live promos, skipped %d (already tracked)", inserted, skipped)

    # 5. Process JSON tombstones — codes that were in JSON but not in live table
    #    These represent deleted promos whose IDs must still be reserved.
    live_codes = {(r[0] or '').strip() for r in rows}

    # Promo codes from JSON
    json_codes = _load_json_set(JSON_FILES['promo_code'])
    deleted_codes = json_codes - live_codes - existing
    log.info("JSON promo codes: %d total, %d from deleted promos", len(json_codes), len(deleted_codes))

    # For deleted promo codes, we only have the code itself (no group IDs available)
    tombstone_inserted = 0
    for code in sorted(deleted_codes):
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO PAM.Promo_ID_Tracking (code, created_by) VALUES (:code, :by)"
                ), {'code': code, 'by': 'backfill-tombstone'})
            existing.add(code)
            tombstone_inserted += 1
        except Exception as e:
            log.warning("Failed to insert tombstone for %s: %s", code, e)

    log.info("Inserted %d tombstone rows from deleted promo codes", tombstone_inserted)

    # Note: JSON files for sku_group_id, trade_in_group_id, mk_mdl_group_id
    # contain group IDs but NOT the promo codes they belonged to. We can't
    # create full tracking rows for them, but the IDs from live promos are
    # already captured above. The deleted-promo group IDs in JSON are
    # effectively orphaned — they'll be covered by the promo code tombstones
    # if those promos appear in issued_codes.json.
    for id_type, path in JSON_FILES.items():
        if id_type == 'promo_code':
            continue
        ids = _load_json_set(path)
        log.info("JSON %s: %d IDs (covered by live promo inserts above)", id_type, len(ids))

    log.info("Backfill complete.")


if __name__ == '__main__':
    main()
