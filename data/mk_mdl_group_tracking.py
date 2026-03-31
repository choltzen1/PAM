"""Make/model group ID allocation algorithms.

mk_mdl group IDs follow the pattern [A-Z]\\d{2} (e.g. A01, A99, Z99).
Total capacity: 26 x 99 = 2,574.

Allocation state is managed by PAM.Promo_ID_Tracking (database table).
JSON tombstone files have been deprecated.
"""
import re
from typing import Set

_PATTERN = re.compile(r'^[A-Z]\d{2}$')
_TOTAL_CAPACITY = 26 * 99  # 2574


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


def allocate_mk_mdl_group_ids(existing_ids: Set[str], count: int) -> list:
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
    'next_mk_mdl_group_id_progressive',
    'allocate_mk_mdl_group_ids',
]
