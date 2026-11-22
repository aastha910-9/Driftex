import pandas as pd
from src.drift import activity
from src.common import C


def test_cleaning_and_aggregation_one_row_per_customer_day():
    C.CUSTOMER_SAMPLE_PCT = 100
    qa = {"null_customer_id": 0, "invalid_timestamp": 0, "duplicate_rows": 0, "rows_used": 0}
    raw = pd.DataFrame({C.COL_CLIENT: [1, 1, 1, None, 2, 2], C.COL_TS: ["2022-10-01 08:00", "2022-10-01 09:00", "2022-10-01 09:00", "2022-10-01", "not a date", "2022-10-02"]})
    ch = activity.clean_chunk(raw, qa)
    assert qa["null_customer_id"] == 1 and qa["invalid_timestamp"] == 1 and qa["duplicate_rows"] == 1
    g = ch.groupby([C.COL_CLIENT, "date"]).size()
    assert g.loc[(1, pd.Timestamp("2022-10-01"))] == 2 and not g.index.duplicated().any()
