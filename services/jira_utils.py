"""Utility helpers for constructing consistent JIRA ticket summary strings.

The summary pattern requested:
  EFPE Promo Device - New Promo - Promo {promo_code} - Orbit {orbit_id} - {initiative_name} - Launch Date {promo_start_date} 12:00 AM

Rules:
- If orbit_id missing, omit the 'Orbit {orbit_id}' segment entirely.
- If initiative_name missing, omit that segment.
- If promo_start_date missing or unparsable, end with 'Launch Date TBD'.
- promo_start_date expected format 'YYYY-MM-DD'.
- Sanitizes initiative_name by stripping common quote characters.
- Collapses any accidental duplicate separators.
"""
from __future__ import annotations
from datetime import datetime
import re

QUOTE_CHARS = "\"'“”‘’`"

def _sanitize(text: str | None) -> str:
    if not text:
        return ''
    # Remove quote characters and trim whitespace
    cleaned = re.sub(f'[{re.escape(QUOTE_CHARS)}]', '', str(text).strip())
    # Collapse internal excessive whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned

def _format_launch_date(promo_start_date: str | None) -> str:
    if not promo_start_date:
        return 'TBD'
    try:
        dt = datetime.strptime(promo_start_date, '%Y-%m-%d')
        # Windows-safe (no leading zeros)
        return f"{dt.month}/{dt.day}/{dt.year} 12:00 AM"
    except ValueError:
        return 'TBD'

def build_jira_summary(
    promo_code: str | None,
    orbit_id: str | None,
    initiative_name: str | None,
    promo_start_date: str | None,
) -> str:
    """Return a standardized JIRA summary string.

    Parameters
    ----------
    promo_code : str | None
        Promotion code; if missing uses '(unknown)'.
    orbit_id : str | None
        Orbit identifier; omitted if missing.
    initiative_name : str | None
        Initiative / bill facing name; omitted if missing.
    promo_start_date : str | None
        Launch date in 'YYYY-MM-DD' expected; if missing/unparseable becomes 'TBD'.
    """
    code = (promo_code or '').strip() or '(unknown)'
    orbit = (orbit_id or '').strip()
    init_name = _sanitize(initiative_name)
    launch_fragment = _format_launch_date(promo_start_date)

    parts = [
        'EFPE Promo Device',
        'New Promo',
        f'Promo {code}'
    ]
    if orbit:
        parts.append(f'Orbit {orbit}')
    if init_name:
        parts.append(init_name)
    parts.append(f'Launch Date {launch_fragment}')

    # Join and ensure no accidental duplicate separators
    summary = ' - '.join(p for p in parts if p)
    # Extra safety: collapse multiple spaces/hyphens
    summary = re.sub(r'\s*-\s*-+', ' - ', summary)
    return summary

__all__ = ['build_jira_summary']

def create_jira_summary(promo_data: dict) -> str:
        """Convenience wrapper to build JIRA summary directly from a promo_data dict.

        Expects keys:
            - code
            - orbit_id
            - initiative_name or bill_facing_name
            - promo_start_date (YYYY-MM-DD)
        Falls back gracefully if keys missing.
        """
        if not isinstance(promo_data, dict):
                return build_jira_summary(None, None, None, None)
        promo_code = promo_data.get('code') or promo_data.get('promo_code') or None
        orbit_id = promo_data.get('orbit_id') or None
        initiative_name = promo_data.get('initiative_name') or promo_data.get('bill_facing_name') or None
        promo_start_date = promo_data.get('promo_start_date') or None
        return build_jira_summary(promo_code, orbit_id, initiative_name, promo_start_date)

__all__.append('create_jira_summary')
