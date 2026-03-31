"""SKU group ID allocation algorithms.

SKU group IDs follow the pattern [A-Z]{2}[1-9] (e.g. AA1, AB5, ZZ9).
Total capacity: 26 x 26 x 9 = 6,084.

Allocation state is managed by PAM.Promo_ID_Tracking (database table).
JSON tombstone files have been deprecated.
"""
import re
import string
from typing import Set

_PATTERN = re.compile(r'^[A-Z]{2}[1-9]$')
_TOTAL_CAPACITY = 26 * 26 * 9  # 6084


def _rank_id(value: str) -> int:
    """Convert a valid id (already pattern matched) to a linear rank."""
    first = ord(value[0]) - 65
    second = ord(value[1]) - 65
    digit = int(value[2]) - 1  # 0..8
    return ((first * 26) + second) * 9 + digit


def _decode_rank(rank: int) -> str:
    first_block = rank // (26 * 9)
    rem = rank % (26 * 9)
    second_block = rem // 9
    digit = (rem % 9) + 1
    return f"{chr(65+first_block)}{chr(65+second_block)}{digit}"


def next_sku_group_id(existing_ids: Set[str]) -> str:
    """Given existing issued IDs, compute the next sequential ID.

    Skips holes by always taking max rank + 1.
    Raises RuntimeError if namespace exhausted.
    """
    valid = [_rank_id(x) for x in existing_ids if _PATTERN.match(x)]
    max_rank = max(valid) if valid else -1
    next_rank = max_rank + 1
    if next_rank >= _TOTAL_CAPACITY:
        raise RuntimeError('SKU group ID namespace exhausted (ZZ9 reached)')
    return _decode_rank(next_rank)


def next_sku_group_id_progressive(existing_ids: Set[str]) -> str:
    """Progressive allocator with safety filtering.

    Design goals:
      * Always progress *sequentially by first letter blocks* (A -> B -> C ...).
      * Treat a block as *exhausted* only when its Z9 terminal (e.g. AZ9) exists.
      * Ignore (do not let them accelerate progression) any IDs whose first letter is
        beyond the *current active block + 1*. These may be legacy or test artifacts.
      * Never backfill holes; we just advance from the highest second-letter+digit
        combination actually issued inside the active block.

    Safety filter rationale: Out-of-band future letters (e.g. U*, T*) should not
    influence selection while earlier blocks are incomplete; they remain tombstoned
    and unavailable for reuse but inert for progression.
    """
    # 1. Collect syntactically valid IDs.
    valid_all = {v for v in existing_ids if _PATTERN.match(v)}
    if not valid_all:
        return 'AA1'

    # 2. Determine the active letter by walking from 'A' upward until we find
    #    a letter whose predecessor (if any) is exhausted (has Z9) but itself not yet exhausted.
    #    If there are no A* entries at all we still *start* at A.
    letters = string.ascii_uppercase

    def block_exhausted(letter: str) -> bool:
        return f"{letter}Z9" in valid_all

    active_letter = 'A'
    # Advance active_letter only if current block exhausted.
    for letter in letters:
        if letter == 'A':
            if block_exhausted('A'):
                active_letter = 'B'
                continue
            active_letter = 'A'
            break
        prev = chr(ord(letter) - 1)
        if active_letter != prev:
            # We have already chosen earlier active block.
            break
        if block_exhausted(prev):
            # Previous exhausted, this becomes candidate active.
            if block_exhausted(letter):
                # This one also exhausted; move forward.
                active_letter = chr(ord(letter) + 1) if letter != 'Z' else 'Z'
                continue
            active_letter = letter
            break
    # Clamp if we ran past 'Z'
    if active_letter > 'Z':
        raise RuntimeError('SKU group ID namespace exhausted (ZZ9 reached)')

    # 3. Safety filter: discard IDs whose first letter is more than +1 ahead of active.
    max_allowed_letter = chr(min(ord('Z'), ord(active_letter) + 1))
    valid_filtered = {v for v in valid_all if v[0] <= max_allowed_letter}

    # 4. Work within the active block for next issuance.
    block_ids = [v for v in valid_filtered if v[0] == active_letter]
    if not block_ids:
        # Starting fresh within this block
        return f'{active_letter}A1'

    # Find highest second letter + digit inside block (no backfill)
    block_ids.sort(key=lambda v: (v[1], int(v[2])))
    last = block_ids[-1]
    second = last[1]
    digit = int(last[2])

    if second == 'Z' and digit == 9:
        # This call observed exhaustion; move to next block start.
        if active_letter == 'Z':
            raise RuntimeError('SKU group ID namespace exhausted (ZZ9 reached)')
        return f'{chr(ord(active_letter)+1)}A1'

    if digit < 9:
        return f'{active_letter}{second}{digit+1}'
    # digit == 9 -> roll to next second letter
    if second == 'Z':
        # Should have hit earlier exhaustion branch; guard anyway.
        if active_letter == 'Z':
            raise RuntimeError('SKU group ID namespace exhausted (ZZ9 reached)')
        return f'{chr(ord(active_letter)+1)}A1'
    return f'{active_letter}{chr(ord(second)+1)}1'


__all__ = [
    'next_sku_group_id',
    'next_sku_group_id_progressive',
]
