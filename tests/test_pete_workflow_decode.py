import pandas as pd

from research.pete_workflow import _decode_df


def test_decode_df_from_json_string():
    df = pd.DataFrame([{'A': 1, 'B': 'x'}])
    raw = df.to_json(orient='split')
    out = _decode_df(raw)
    assert list(out.columns) == ['A', 'B']
    assert out.iloc[0]['A'] == 1
    assert out.iloc[0]['B'] == 'x'
