import json
import os
import re
from typing import Set

ISSUED_TRADE_IN_GROUPS_FILE = os.path.join('data', 'issued_trade_in_groups.json')

# Trade-in group IDs follow Letter + 2 digits pattern (A01..A99, B01..B99, ..., Z99)
_PATTERN = re.compile(r'^[A-Z]\d{2}$')
_TOTAL_CAPACITY = 26 * 99  # 2574


def _ensure_file():
    os.makedirs(os.path.dirname(ISSUED_TRADE_IN_GROUPS_FILE), exist_ok=True)
    if not os.path.exists(ISSUED_TRADE_IN_GROUPS_FILE):
        with open(ISSUED_TRADE_IN_GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)


def load_issued_trade_in_group_ids() -> Set[str]:
    try:
        _ensure_file()
        with open(ISSUED_TRADE_IN_GROUPS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return {x for x in data if isinstance(x, str) and _PATTERN.match(x)}
            return set()
    except Exception:
        return set()


def record_issued_trade_in_group_id(trade_in_group_id: str):
    if not trade_in_group_id or not _PATTERN.match(trade_in_group_id):
        return
    try:
        issued = load_issued_trade_in_group_ids()
        if trade_in_group_id in issued:
            return
        issued.add(trade_in_group_id)
        tmp = ISSUED_TRADE_IN_GROUPS_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(sorted(issued), f)
        os.replace(tmp, ISSUED_TRADE_IN_GROUPS_FILE)
    except Exception:
        pass


def _rank_id(value: str) -> int:
    """Convert e.g. N92 to linear rank. A01=0, A99=98, B01=99, ..."""
    letter = ord(value[0]) - 65
    num = int(value[1:]) - 1  # 01->0, 99->98
    return letter * 99 + num


def _decode_rank(rank: int) -> str:
    letter = rank // 99
    num = (rank % 99) + 1
    return f"{chr(65 + letter)}{num:02d}"


def next_trade_in_group_id_progressive(existing_ids: Set[str]) -> str:
    """Return the next trade-in group ID after the highest existing one.

    Format: Letter + 2 digits (A01..Z99). Progresses sequentially.
    """
    valid = {v for v in existing_ids if _PATTERN.match(v)}
    if not valid:
        return 'A01'

    max_rank = max(_rank_id(v) for v in valid)
    next_rank = max_rank + 1
    if next_rank >= _TOTAL_CAPACITY:
        raise RuntimeError('Trade-in group ID namespace exhausted (Z99 reached)')
    return _decode_rank(next_rank)


__all__ = [
    'load_issued_trade_in_group_ids',
    'record_issued_trade_in_group_id',
    'next_trade_in_group_id_progressive',
]
