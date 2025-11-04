import pandas as pd
from research.pete_workflow import normalize_datetime_columns

def test_normalize_datetime_columns_epoch_ms():
    df = pd.DataFrame({
        'SYS_CREATION_DATE': [1748390400000, 1748390400000],
        'OTHER': [1, 2]
    })
    out = normalize_datetime_columns(df)
    # Build expected via same conversion logic
    expected = pd.to_datetime(df['SYS_CREATION_DATE'], unit='ms', utc=True).dt.tz_convert(None).dt.strftime('%Y-%m-%d')[0]
    assert out['SYS_CREATION_DATE'].iloc[0] == expected
    assert len(out['SYS_CREATION_DATE'].iloc[0]) == 10  # YYYY-MM-DD


def test_normalize_datetime_columns_epoch_seconds():
    # Use a seconds epoch (~ Jan 15 2025)
    seconds_val = 1736899200  # 2024-12-15? (Exact date not critical for formatting)
    df = pd.DataFrame({
        'PLAN_START_DATE': [seconds_val, seconds_val],
        'X': [10, 11]
    })
    out = normalize_datetime_columns(df)
    expected = pd.to_datetime(df['PLAN_START_DATE'], unit='s', utc=True).dt.tz_convert(None).dt.strftime('%Y-%m-%d')[0]
    assert out['PLAN_START_DATE'].iloc[0] == expected
    assert '-' in out['PLAN_START_DATE'].iloc[0]
