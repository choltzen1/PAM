import json, os, sqlite3, sys
from datetime import datetime
from data.database import DatabaseManager

EXTRAS_FIELDS = [
    'jira_ticket','initiative_name','sku_link','tradein_link','promo_grace','trade_in_grace',
    'segment_name','sub_segment','segment_group_id','segment_level','flow_indicator'
]

PROMO_JSON = os.path.join('data','promotions.json')

def load_promos():
    paths = [PROMO_JSON, PROMO_JSON + '.bak']
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p,'r',encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                continue
    return {}

def main(dry_run: bool = True):
    promos = load_promos()
    if not promos:
        print('No promos loaded or file missing.')
        return
    dm = DatabaseManager()
    migrated = 0
    skipped = 0
    for code, pdata in promos.items():
        extras = {k: pdata.get(k) for k in EXTRAS_FIELDS if k in pdata and pdata.get(k) not in (None,'')}
        if not extras:
            skipped += 1
            continue
        if dry_run:
            print(f"[DRY] Would migrate {code}: {extras}")
        else:
            dm.upsert_promo_extras(code, extras, user='MigrationScript')
            print(f"Migrated {code}: {list(extras.keys())}")
        migrated += 1
    print(f"Done. Migrated {migrated} (with extras present), skipped {skipped} (no extras).")

if __name__ == '__main__':
    dry = '--apply' not in sys.argv
    if dry:
        print('Running in dry-run mode. Use --apply to persist changes.')
    main(dry_run=dry)
