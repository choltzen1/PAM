"""Trade-in group ID allocation algorithms.

Trade-in group IDs follow the pattern [A-Z]\\d{2} (e.g. A01, A99, Z99).
Total capacity: 26 x 99 = 2,574.

Allocation state is managed by PAM.Promo_ID_Tracking (database table).
JSON tombstone files have been deprecated.
"""
import re
from typing import Set

_PATTERN = re.compile(r'^[A-Z]\d{2}$')
_TOTAL_CAPACITY = 26 * 99  # 2574


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
    'next_trade_in_group_id_progressive',
]
