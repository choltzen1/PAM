"""Export non-null promo codes from Orbit source table into INSERT statements for PAM database.

Usage (PowerShell):
  python tools/export_orbit_to_pam.py --output orbit_pam_seed.sql --batch-size 500

Environment:
    Reuses existing env vars for DB connection (PAM_DB_*). Assumes table [PAM].[PAM_Orbit_Data_Updated].

The script will:
 1. Connect to source (Orbit) using DatabaseManager credentials.
 2. Pull all rows where code IS NOT NULL AND code <> 'NULL'.
 3. Generate batched INSERT statements for a target table you specify (default: PAM.dbo.Promotions).
 4. Quote/escape string values, format dates, and convert None to NULL.

Adjust TARGET_COLUMNS to match the destination schema.
"""
from __future__ import annotations
import os
import sys
import argparse
import math
from typing import List, Dict, Any, Sequence
from data.database import DatabaseManager
from sqlalchemy import text

# Map source column order -> target column names.
# Adjust to match PAM destination schema exactly.
TARGET_TABLE = os.getenv('PAM_TARGET_TABLE', 'PAM.dbo.Promotions')
# Columns we will select from source (must exist in Orbit table)
SOURCE_COLUMNS = [
    'code','Owner','bill facing name','orbit_id','description','promo_notes','discount','amount',
    'nseip_drop','dcd_web_cart','product_type','bogo','fpd_display_promo','on_menu','market_group','store_group',
    'promo_start_date','promo_end_date','comm_end_date','promo_duration','delay_time','application_grace_period',
    'device_sales_type','activation_type','active_line_required','maintain_soc','crffc_maintainactivelinedev',
    'limit_per_ban','soc_grouping','account_type','sales_application','operator_id','sku_group_id',
    'device_status_group_id','clawback_indicator','Broken_Trade','Anticipated_volume_take_rates_total','Desired_Execution'
]
# Target columns: rename spaces / reserved words as needed.
TARGET_COLUMNS = [
    'code','owner','bill_facing_name','orbit_id','description','promo_notes','discount','amount',
    'nseip_drop','dcd_web_cart','product_type','bogo','fpd_display_promo','on_menu','market_group','store_group',
    'promo_start_date','promo_end_date','comm_end_date','promo_duration','delay_time','application_grace_period',
    'device_sales_type','activation_type','active_line_required','maintain_soc','crffc_maintainactivelinedev',
    'limit_per_ban','soc_grouping','account_type','sales_application','operator_id','sku_group_id',
    'device_status_group_id','clawback_indicator','broken_trade','anticipated_volume_take_rates_total','desired_execution'
]
if len(SOURCE_COLUMNS) != len(TARGET_COLUMNS):
    raise SystemExit('SOURCE_COLUMNS and TARGET_COLUMNS length mismatch.')

ESCAPE_SINGLE = lambda s: s.replace("'", "''")

DATE_INPUT_FORMATS = ('%m/%d/%Y','%Y-%m-%d','%m/%d/%y')
from datetime import datetime

def normalize_date(val: Any) -> str:
    if val is None:
        return 'NULL'
    s = str(val).strip()
    if not s or s.upper() == 'NULL':
        return 'NULL'
    for fmt in DATE_INPUT_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return f"'{dt.strftime('%Y-%m-%d')}'"
        except Exception:
            continue
    # Leave raw if not parseable
    return f"'{ESCAPE_SINGLE(s)}'"

def sql_literal(val: Any, is_date: bool = False) -> str:
    if val is None:
        return 'NULL'
    if isinstance(val, (int,float)) and not isinstance(val, bool):
        return str(val)
    s = str(val).strip()
    if s.upper() == 'NULL':
        return 'NULL'
    if is_date:
        return normalize_date(s)
    # Treat empty string as NULL? Keep empty quoted to preserve original unless flagged.
    return f"'{ESCAPE_SINGLE(s)}'"

DATE_SOURCE_INDEXES = {SOURCE_COLUMNS.index(c) for c in ['promo_start_date','promo_end_date','comm_end_date']}

FETCH_SQL = f"""
SELECT {', '.join(f'[{c}]' if ' ' in c else c for c in SOURCE_COLUMNS)}
FROM [PAM].[PAM_Orbit_Data_Updated]
WHERE code IS NOT NULL AND code <> 'NULL'
ORDER BY code
"""

def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i+size]

def build_insert_rows(rows: Sequence[Sequence[Any]]) -> List[str]:
    insert_rows = []
    for r in rows:
        values_sql = []
        for idx, val in enumerate(r):
            is_date = idx in DATE_SOURCE_INDEXES
            values_sql.append(sql_literal(val, is_date))
        insert_rows.append(f"({', '.join(values_sql)})")
    return insert_rows

def main():
    ap = argparse.ArgumentParser(description='Export Orbit promos to INSERT statements for PAM DB')
    ap.add_argument('--output','-o', default='orbit_pam_seed.sql', help='Output .sql file')
    ap.add_argument('--batch-size','-b', type=int, default=500, help='Rows per INSERT statement')
    ap.add_argument('--target-table','-t', default=TARGET_TABLE, help='Override target table name')
    args = ap.parse_args()

    mgr = DatabaseManager()
    engine = mgr.get_engine()
    with engine.connect() as conn:
        res = conn.execute(text(FETCH_SQL))
        data = res.fetchall()
    total = len(data)
    if total == 0:
        print('No rows found.')
        return

    print(f"Fetched {total} rows. Building INSERT statements...")
    inserts: List[str] = []
    col_list = ', '.join(f'[{c}]' for c in TARGET_COLUMNS)
    for batch in chunked(data, args.batch_size):
        # Convert SQLAlchemy Row objects to tuples
        tuple_batch = [tuple(r) for r in batch]
        rows_sql = build_insert_rows(tuple_batch)
        inserts.append(f"INSERT INTO {args.target_table} ({col_list}) VALUES\n  " + ",\n  ".join(rows_sql) + ";")

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write('-- Generated Orbit -> PAM seed script\n')
        f.write(f'-- Source rows: {total}\n')
        for stmt in inserts:
            f.write(stmt + '\n')
    print(f"Wrote {len(inserts)} INSERT statements to {args.output}")

if __name__ == '__main__':
    main()
