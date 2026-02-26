import argparse
from sqlalchemy import text

from data.database import DatabaseManager


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize legacy ZLAB event_type values.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates to PAM.Version_History (default is dry run).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    dm = DatabaseManager()
    engine = dm.get_engine()

    count_sql = (
        "SELECT COUNT(1) AS cnt FROM PAM.Version_History "
        "WHERE event_type LIKE 'zlab testing insert%'"
    )
    update_sql = (
        "UPDATE PAM.Version_History "
        "SET event_type = CASE "
        "WHEN event_type LIKE '%failed%' THEN 'zlab_insert_failed' "
        "ELSE 'zlab_inserted' END "
        "WHERE event_type LIKE 'zlab testing insert%'"
    )

    with engine.begin() as conn:
        total = conn.execute(text(count_sql)).scalar() or 0
        print(f"Legacy ZLAB rows found: {total}")
        if not args.apply:
            print("Dry run only. Re-run with --apply to update.")
            return 0
        if total:
            conn.execute(text(update_sql))
            print("Backfill complete.")
        else:
            print("No rows to update.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
