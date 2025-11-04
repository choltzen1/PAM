import pandas as pd
from research.pete_workflow import normalize_datetime_columns

def test_does_not_convert_plain_id_columns():
    df = pd.DataFrame({
        'ID': [1748390400000, 1748390400001],  # looks like ms epoch but is an ID
        'DISCOUNTED_EQUIPMENT_ID': [1748390400002, 1748390400003],
        'SYS_CREATION_DATE': [1748390400000, 1748390400000]
    })
    out = normalize_datetime_columns(df)
    # Date column should convert
    assert out['SYS_CREATION_DATE'].iloc[0].startswith('2025') or out['SYS_CREATION_DATE'].iloc[0].startswith('2024')
    # ID columns should remain numeric (type/object check: unchanged values)
    assert out['ID'].iloc[0] == 1748390400000
    assert out['DISCOUNTED_EQUIPMENT_ID'].iloc[0] == 1748390400002
