import pandas as pd
from research.pete_workflow import normalize_datetime_columns

def test_force_datetime_column_converts():
    # Simulate epoch ms values in a column lacking date hints but force-listed
    df = pd.DataFrame({
        'LAST_EVENT_OCCURRED': [1748390400000, 1748394000000],
        'ID': [111, 222]
    })
    out = normalize_datetime_columns(df)
    # Forced column should convert to date strings
    assert isinstance(out['LAST_EVENT_OCCURRED'].iloc[0], str)
    assert out['LAST_EVENT_OCCURRED'].iloc[0].count('-') == 2
    # ID should remain numeric
    assert out['ID'].iloc[0] == 111
