"""Parse crffc_eligibletradeindevices text into structured trade tiers.

Example input:
  $830 Tier:  Apple: 11 Pro, 11 Pro Max, 12, ...  Samsung Galaxy: S9, S9+, ...
  $415 tier:  Apple iPhone: 6, 6 Plus, ...  Samsung Galaxy: S8, S8+, ...

Output: list of dicts sorted by amount descending (tier 1 = highest value).
  [{'amount': 830, 'raw_text': '...'}, {'amount': 415, 'raw_text': '...'}]
"""
import re
from typing import List, Dict, Any


def parse_trade_tiers(text: str) -> List[Dict[str, Any]]:
    """Parse the eligible trade-in devices text into tiers.

    Returns list sorted by amount descending (highest first = tier 1).
    Each entry: {'amount': int, 'raw_text': str}
    """
    if not text or not text.strip():
        return []

    # Find all "$NNN Tier:" patterns and split the text at those boundaries
    # Pattern matches $XXX followed by optional space and "tier" (case-insensitive)
    tier_pattern = re.compile(r'\$(\d+)\s*[Tt]ier\s*:', re.IGNORECASE)

    matches = list(tier_pattern.finditer(text))
    if not matches:
        return []

    tiers = []
    for i, match in enumerate(matches):
        amount = int(match.group(1))
        start = match.end()
        # Text runs until the next tier marker or end of string
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        raw_text = text[start:end].strip()
        tiers.append({
            'amount': amount,
            'raw_text': raw_text,
        })

    # Sort descending by amount (tier 1 = highest value)
    tiers.sort(key=lambda t: t['amount'], reverse=True)

    return tiers


def build_trade_tier_fields(
    tiers: List[Dict[str, Any]],
    mk_mdl_group_ids: List[str],
    condition_id: str,
) -> Dict[str, Any]:
    """Build the PAM field dict for up to 4 trade tiers.

    Args:
        tiers: Parsed tiers from parse_trade_tiers(), sorted highest amount first.
        mk_mdl_group_ids: Allocated IDs (one per tier, lowest ID = tier 1).
        condition_id: 'ST1' for standard or 'BT1' for broken trade.

    Returns:
        Dict of field names to values for insertion into PAM table.
    """
    fields: Dict[str, Any] = {}
    max_tiers = min(len(tiers), len(mk_mdl_group_ids), 4)

    for i in range(max_tiers):
        tier_num = i + 1
        fields[f'mk_mdl_grp_tier_{tier_num}'] = mk_mdl_group_ids[i]
        fields[f'mk_mdl_grp_tier_{tier_num}_amount'] = str(tiers[i]['amount'])
        fields[f'mk_mdl_grp_tier_{tier_num}_condition_id'] = condition_id

    return fields


__all__ = ['parse_trade_tiers', 'build_trade_tier_fields']
