"""Migrate legacy JSON promo version histories into SQLite version_history + date_diagnostics tables.

Usage (PowerShell):
  python tools/migrate_json_history.py --apply

Behavior:
- Reads data/promotions.json, data/spe_promotions.json, data/rebates.json if present.
- For each promo, extracts its code and version_history list.
- Inserts entries into version_history table if they are not already present (basic duplicate check by (promo_code, entry text, timestamp substring)).
- Stores a synthetic change_type based on prefix patterns:
    'PCR version #' -> 'PCR Version'
    'Approval sent out' -> 'Approval'
    'Created promo' -> 'Created'
    'Created SPE promo' -> 'Created'
    else 'History'
- Leaves original JSON untouched; can be re-run safely (idempotent-ish) due to duplicate skip logic.
"""
from __future__ import annotations
import os, json, argparse, sqlite3, re
from datetime import datetime

DATA_DIR = 'data'
PROMO_JSON = os.path.join(DATA_DIR, 'promotions.json')
SPE_JSON = os.path.join(DATA_DIR, 'spe_promotions.json')
REBATES_JSON = os.path.join(DATA_DIR, 'rebates.json')
DB_PATH = os.path.join(DATA_DIR, 'version_history.db')

PATTERNS = [
    (re.compile(r'PCR version #', re.IGNORECASE), 'PCR Version'),
    (re.compile(r'Approval sent out', re.IGNORECASE), 'Approval'),
    (re.compile(r'Created (SPE )?promo', re.IGNORECASE), 'Created'),
]

def classify(entry: str) -> str:
    for pat, label in PATTERNS:
        if pat.search(entry):
            return label
    return 'History'

def load_json(path: str):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS version_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    promo_code TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    change_type TEXT NOT NULL,
    description TEXT NOT NULL
)
"""

INSERT_SQL = "INSERT INTO version_history (promo_code, timestamp, change_type, description) VALUES (?,?,?,?)"

# Simple duplicate detection query
SELECT_EXISTING = "SELECT 1 FROM version_history WHERE promo_code=? AND description=? LIMIT 1"

def parse_timestamp(entry: str) -> str:
    # Expect leading 'MM/DD/YYYY HH:MM AM/PM -' pattern
    try:
        prefix = entry.split(' - ')[0]
        dt = datetime.strptime(prefix, '%m/%d/%Y %I:%M %p')
        return dt.isoformat()
    except Exception:
        return datetime.utcnow().isoformat()


def migrate(entries: dict, conn: sqlite3.Connection, spe: bool=False):
    cur = conn.cursor()
    inserted = 0
    for code, pdata in entries.items():
        if not code:
            continue
        history = pdata.get('version_history') or []
        for h in history:
            ts = parse_timestamp(h)
            ctype = classify(h)
            cur.execute(SELECT_EXISTING, (code, h))
            if cur.fetchone():
                continue
            cur.execute(INSERT_SQL, (code, ts, ctype, h))
            inserted += 1
    return inserted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='Execute migration (otherwise dry run)')
    args = ap.parse_args()

    promos = load_json(PROMO_JSON)
    spe = load_json(SPE_JSON)
    rebates = load_json(REBATES_JSON)

    # Normalize possible list structures to dict keyed by code
    def list_to_dict(obj):
        if isinstance(obj, list):
            out = {}
            for item in obj:
                if isinstance(item, dict):
                    code = item.get('code') or item.get('promo_code') or ''
                    if code:
                        out[code] = item
            return out
        return obj
    promos = list_to_dict(promos)
    spe = list_to_dict(spe)
    rebates = list_to_dict(rebates)

    if not (promos or spe or rebates):
        print('No JSON data files found. Nothing to migrate.')
        return

    print(f"Loaded counts: promos={len(promos)} spe={len(spe)} rebates={len(rebates)}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(CREATE_SQL)
        if not args.apply:
            promo_ins = sum(len(p.get('version_history') or []) for p in promos.values())
            spe_ins = sum(len(p.get('version_history') or []) for p in spe.values())
            reb_ins = sum(len(p.get('version_history') or []) for p in rebates.values())
            total = promo_ins + spe_ins + reb_ins
            print(f"Dry run: would attempt {total} history inserts (promo={promo_ins}, spe={spe_ins}, rebate={reb_ins})")
            print('Re-run with --apply to commit.')
            return
        promo_added = migrate(promos, conn)
        spe_added = migrate(spe, conn, spe=True)
        rebate_added = migrate(rebates, conn)
        print(f"Inserted history rows: promo={promo_added} spe={spe_added} rebate={rebate_added} total={promo_added+spe_added+rebate_added}")
        conn.commit()

if __name__ == '__main__':
    main()
