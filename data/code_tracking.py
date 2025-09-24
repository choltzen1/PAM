import json
import os
from typing import Set

ISSUED_CODES_FILE = os.path.join('data', 'issued_codes.json')


def _ensure_file():
    os.makedirs(os.path.dirname(ISSUED_CODES_FILE), exist_ok=True)
    if not os.path.exists(ISSUED_CODES_FILE):
        with open(ISSUED_CODES_FILE, 'w') as f:
            json.dump([], f)


def load_issued_codes() -> Set[str]:
    """Load previously issued promo codes (tombstones) so we never reuse them after deletion."""
    try:
        _ensure_file()
        with open(ISSUED_CODES_FILE, 'r') as f:
            data = json.load(f)
            if isinstance(data, list):
                return set([c for c in data if isinstance(c, str)])
            return set()
    except Exception:
        return set()


def record_issued_code(code: str):
    """Persist a newly issued code to prevent future reuse, even if later deleted."""
    if not code:
        return
    try:
        issued = load_issued_codes()
        if code in issued:
            return
        issued.add(code)
        # Write atomically
        tmp_file = ISSUED_CODES_FILE + '.tmp'
        with open(tmp_file, 'w') as f:
            json.dump(sorted(list(issued)), f)
        os.replace(tmp_file, ISSUED_CODES_FILE)
    except Exception:
        # Non-fatal; failure only risks possible reuse
        pass
