import re
from services.jira_utils import build_jira_summary


def test_full_summary():
    s = build_jira_summary('ABC123', '7890', 'My Initiative', '2025-11-20')
    assert s.startswith('EFPE Promo Device - New Promo - Promo ABC123 - Orbit 7890 - My Initiative - Launch Date')
    assert '11/20/2025 12:00 AM' in s
    assert ' -  - ' not in s


def test_missing_orbit():
    s = build_jira_summary('ABC123', None, 'Launch Thing', '2025-01-05')
    assert 'Orbit' not in s
    assert 'Promo ABC123 - Launch Thing - Launch Date 1/5/2025 12:00 AM' in s


def test_missing_initiative():
    s = build_jira_summary('CODE1', '9999', None, '2025-02-02')
    assert 'Orbit 9999 - Launch Date 2/2/2025 12:00 AM' in s
    # Ensure no trailing spaces/hyphens before Launch Date
    assert re.search(r'Orbit 9999 - Launch Date', s) is not None


def test_missing_date():
    s = build_jira_summary('PROMO7', '1234', 'Thing', None)
    assert s.endswith('Launch Date TBD')


def test_invalid_date_format():
    s = build_jira_summary('PROMO8', '1234', 'Thing', '11/20/2025')  # wrong format
    assert s.endswith('Launch Date TBD')


def test_unknown_code():
    s = build_jira_summary(None, '12', 'Init', '2025-03-10')
    assert 'Promo (unknown)' in s


def test_initiative_sanitization_quotes_removed():
    raw_name = '"Fancy" Initiative \"Test\"'
    s = build_jira_summary('PROMO9', '55', raw_name, '2025-04-03')
    assert 'Fancy Initiative Test' in s
    assert '"' not in s
    assert '\'' not in s


def test_no_double_separators():
    # Missing orbit & initiative
    s = build_jira_summary('PROMO10', None, None, '2025-05-06')
    assert ' -  - ' not in s
    # Ensure pattern sequence count of ' - ' matches expected segments (Promo, Launch Date)
    parts = s.split(' - ')
    # EFPE Promo Device, New Promo, Promo PROMO10, Launch Date ... => 4 parts
    assert len(parts) == 4
