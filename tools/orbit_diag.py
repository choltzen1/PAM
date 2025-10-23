"""Orbit table diagnostic tool.

Runs the same query used by orbit_search and prints either the first matching
row for a provided orbit id, or a count of rows in the table if no id given.

Usage (PowerShell):
  python tools/orbit_diag.py --orbit-id ORB123
  python tools/orbit_diag.py --sample 5

Environment variables override connection:
  ORBIT_DB_SERVER, ORBIT_DB_DATABASE, ORBIT_DB_USERNAME, ORBIT_DB_PASSWORD,
  ORBIT_DB_DRIVER, ORBIT_DB_ENCRYPT, ORBIT_DB_TRUST_CERT, ORBIT_TABLE
"""
import os
import argparse
import json
from data.orbit_database import OrbitDatabaseManager

def build_conn_str():
    # Deprecated: retained for backward compatibility. Use OrbitDatabaseManager instead.
    return ''

def main():
    parser = argparse.ArgumentParser(description="Orbit table diagnostic")
    parser.add_argument('--orbit-id', help='Orbit ID to fetch')
    parser.add_argument('--sample', type=int, default=0, help='List first N orbit_ids')
    args = parser.parse_args()
    mgr = OrbitDatabaseManager()
    if args.orbit_id:
        rec = mgr.get_orbit_record(args.orbit_id)
        if not rec:
            print(f'NOT FOUND: {args.orbit_id}')
        else:
            print('ROW:', json.dumps(rec, indent=2))
    elif args.sample > 0:
        ids = mgr.list_orbit_ids(args.sample)
        print(f'SAMPLE ({len(ids)}):', ids)
    else:
        cols = mgr.get_columns()
        print('COLUMNS:', cols)
    return 0
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
