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

    Splits on $NNN boundaries — handles any format:
      $830 Tier: ...
      $830: ...
      $830 Apple: ...

    Returns list sorted by amount descending (highest first = tier 1).
    Each entry: {'amount': int, 'raw_text': str}
    """
    if not text or not text.strip():
        return []

    # Match any $NNN pattern (dollar sign + digits) as a tier boundary
    tier_pattern = re.compile(r'\$(\d+)')

    matches = list(tier_pattern.finditer(text))
    if not matches:
        return []

    # Deduplicate amounts (same dollar value appearing multiple times = same tier)
    seen_amounts = set()
    tiers = []
    for i, match in enumerate(matches):
        amount = int(match.group(1))
        if amount in seen_amounts:
            continue
        seen_amounts.add(amount)
        start = match.end()
        # Text runs until the next $NNN marker or end of string
        next_match = None
        for j in range(i + 1, len(matches)):
            if int(matches[j].group(1)) not in seen_amounts or int(matches[j].group(1)) != amount:
                next_match = matches[j]
                break
        end = next_match.start() if next_match else len(text)
        raw_text = text[start:end].strip()
        # Strip optional "Tier:" or "tier:" prefix from raw_text
        raw_text = re.sub(r'^[Tt]ier\s*:\s*', '', raw_text)
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
