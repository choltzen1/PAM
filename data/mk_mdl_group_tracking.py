import json
import os
import re
from typing import Set

ISSUED_MK_MDL_GROUPS_FILE = os.path.join('data', 'issued_mk_mdl_groups.json')

# mk_mdl group IDs follow Letter + 2 digits pattern (A01..A99, B01..B99, ..., Z99)
_PATTERN = re.compile(r'^[A-Z]\d{2}$')
_TOTAL_CAPACITY = 26 * 99  # 2574


def _ensure_file():
    os.makedirs(os.path.dirname(ISSUED_MK_MDL_GROUPS_FILE), exist_ok=True)
    if not os.path.exists(ISSUED_MK_MDL_GROUPS_FILE):
        with open(ISSUED_MK_MDL_GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)


def load_issued_mk_mdl_group_ids() -> Set[str]:
    try:
        _ensure_file()
        with open(ISSUED_MK_MDL_GROUPS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return {x for x in data if isinstance(x, str) and _PATTERN.match(x)}
            return set()
    except Exception:
        return set()


def record_issued_mk_mdl_group_id(mk_mdl_group_id: str):
    if not mk_mdl_group_id or not _PATTERN.match(mk_mdl_group_id):
        return
    try:
        issued = load_issued_mk_mdl_group_ids()
        if mk_mdl_group_id in issued:
            return
        issued.add(mk_mdl_group_id)
        tmp = ISSUED_MK_MDL_GROUPS_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(sorted(issued), f)
        os.replace(tmp, ISSUED_MK_MDL_GROUPS_FILE)
    except Exception:
        pass


def _rank_id(value: str) -> int:
    letter = ord(value[0]) - 65
    num = int(value[1:]) - 1
    return letter * 99 + num


def _decode_rank(rank: int) -> str:
    letter = rank // 99
    num = (rank % 99) + 1
    return f"{chr(65 + letter)}{num:02d}"


def next_mk_mdl_group_id_progressive(existing_ids: Set[str]) -> str:
    """Return the next mk_mdl group ID after the highest existing one."""
    valid = {v for v in existing_ids if _PATTERN.match(v)}
    if not valid:
        return 'A01'

    max_rank = max(_rank_id(v) for v in valid)
    next_rank = max_rank + 1
    if next_rank >= _TOTAL_CAPACITY:
        raise RuntimeError('mk_mdl group ID namespace exhausted (Z99 reached)')
    return _decode_rank(next_rank)


def allocate_mk_mdl_group_ids(existing_ids: Set[str], count: int) -> list[str]:
    """Allocate multiple sequential mk_mdl group IDs at once.

    Returns list of `count` new IDs. Lowest ID = tier 1 (highest dollar amount).
    """
    allocated = []
    current = set(existing_ids)
    for _ in range(count):
        new_id = next_mk_mdl_group_id_progressive(current)
        allocated.append(new_id)
        current.add(new_id)
    return allocated


__all__ = [
    'load_issued_mk_mdl_group_ids',
    'record_issued_mk_mdl_group_id',
    'next_mk_mdl_group_id_progressive',
    'allocate_mk_mdl_group_ids',
]
