import sys
from data.schema_reference import refresh_staging_reference


def main() -> int:
    try:
        data = refresh_staging_reference()
        print(f"Staging reference updated: {data.get('staging_reference')} (live: {data.get('live_reference')})")
        return 0
    except Exception as exc:
        print(f"Failed to refresh staging reference: {exc}")
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
