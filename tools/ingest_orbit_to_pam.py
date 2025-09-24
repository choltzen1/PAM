"""Bulk ingest Orbit RDC records into PAM JSON storage.

Usage (PowerShell):
    python -m tools.ingest_orbit_to_pam            # live ingest (RDC only)
    python -m tools.ingest_orbit_to_pam --dry-run  # preview without writing
    python -m tools.ingest_orbit_to_pam --limit 100

Behavior:
- Always targets Desired_Execution='RDC'.
- Reads existing PAM JSON promotions (promotions.json); skips existing codes unless --overwrite.
- Converts each DB row with convert_db_record_to_json_format.
- Timestamped backup (unless --no-backup) before write.
- Dry-run mode shows planned adds/skips only.

Note: JSON-layer only; future direct DB storage will deprecate this script.
"""
from __future__ import annotations
import argparse, os, json, datetime, sys
from typing import List

# Ensure project root on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data.database import DatabaseManager  # type: ignore
from data.storage import PromoDataManager  # type: ignore


def load_json(path: str) -> dict:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_json(path: str, data: dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def backup_file(path: str) -> str:
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    base = os.path.basename(path)
    bdir = os.path.join('backups', f'bulk_ingest_{ts}')
    os.makedirs(bdir, exist_ok=True)
    dest = os.path.join(bdir, base)
    try:
        import shutil
        shutil.copy2(path, dest)
    except FileNotFoundError:
        pass
    return dest


def fetch_rdc_records(limit: int | None) -> List[dict]:
    dbm = DatabaseManager()
    records = dbm.get_promos_by_execution_type('RDC')
    if limit is not None:
        records = records[:limit]
    return records


def convert_records(records: List[dict], dbm: DatabaseManager) -> List[dict]:
    converted = []
    for rec in records:
        try:
            converted.append(dbm.convert_db_record_to_json_format(rec))
        except Exception as e:
            print(f"Conversion failed for code={rec.get('code')}: {e}")
    return converted


def merge_into_pam(existing: dict, new_recs: List[dict], overwrite: bool) -> tuple[int,int]:
    added = 0
    skipped = 0
    for rec in new_recs:
        code = rec.get('code')
        if not code:
            skipped += 1
            continue
        if code in existing and not overwrite:
            skipped += 1
            continue
        # Ensure code field persisted inside object
        if 'code' not in rec:
            rec['code'] = code
        existing[code] = rec
        added += 1
    return added, skipped


def main():
    ap = argparse.ArgumentParser(description='Ingest Orbit data into PAM JSON promotions.')
    # Execution type fixed to RDC; flag retained only for backward compatibility (ignored if provided)
    ap.add_argument('--execution-types','-t', nargs='*', help='(Ignored) Execution types; script now fixed to RDC')
    ap.add_argument('--limit', type=int, default=None, help='Optional limit on number of DB rows processed')
    ap.add_argument('--dry-run', action='store_true', help='Do not write any files; just report stats')
    ap.add_argument('--overwrite', action='store_true', help='Overwrite existing promo codes in JSON')
    ap.add_argument('--no-backup', action='store_true', help='Skip automatic backup creation')
    args = ap.parse_args()

    data_dir = 'data'
    promos_path = os.path.join(data_dir, 'promotions.json')

    print('Loading existing PAM promotions JSON...')
    existing = load_json(promos_path)
    existing_count = len(existing)
    print(f'Existing promotions count: {existing_count}')

    print("Fetching Orbit RDC records...")
    dbm = DatabaseManager()
    raw_records = fetch_rdc_records(args.limit)
    print(f'Database records fetched: {len(raw_records)}')

    print('Converting records to PAM JSON schema...')
    converted = convert_records(raw_records, dbm)
    print(f'Converted successfully: {len(converted)}')

    print('Merging into JSON set...')
    added, skipped = merge_into_pam(existing, converted, args.overwrite)

    print('Summary:')
    print(f'  Existing before: {existing_count}')
    print(f'  Added: {added}')
    print(f'  Skipped (pre-existing or invalid): {skipped}')
    print(f'  Final count (would be): {len(existing)}')

    if args.dry_run:
        print('Dry-run mode: no file changes written.')
        return

    if not args.no_backup:
        backup_loc = backup_file(promos_path)
        print(f'Backup created at: {backup_loc}')

    print('Writing merged promotions JSON...')
    save_json(promos_path, existing)
    print('Done.')

if __name__ == '__main__':
    main()
