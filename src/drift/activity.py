"""Customer-day activity aggregation (Shaffy).
Reads the five event files in chunks, cleans them and writes data/processed/customer_daily_activity.csv
(one row per customer_id + date). Qualifying activity = any logged event:
page visit, search, add-to-cart, remove-from-cart, purchase."""
import json
import pandas as pd
from src.common import C, activity_path
from io_utils import iter_chunks, read_all

EVENTS = {"visits": "page_visit", "searches": "search_query", "carts": "add_to_cart",
          "removes": "remove_from_cart", "buys": "product_buy"}


def clean_chunk(ch, qa):
    """Validity checks: null ids, invalid timestamps, exact duplicate rows, hash-sample of customers."""
    n0 = len(ch)
    ch = ch.dropna(subset=[C.COL_CLIENT]); qa["null_customer_id"] += n0 - len(ch)
    ch = ch[(ch[C.COL_CLIENT].astype("int64") % 100) < C.CUSTOMER_SAMPLE_PCT]
    ch = ch.assign(date=pd.to_datetime(ch[C.COL_TS], errors="coerce", format="mixed").dt.floor("D"))
    n1 = len(ch); ch = ch.dropna(subset=["date"]); qa["invalid_timestamp"] += n1 - len(ch)
    n2 = len(ch); ch = ch.drop_duplicates(); qa["duplicate_rows"] += n2 - len(ch)
    ch[C.COL_CLIENT] = ch[C.COL_CLIENT].astype("int64")
    qa["rows_used"] += len(ch)
    return ch


def build():
    qa = {"null_customer_id": 0, "invalid_timestamp": 0, "duplicate_rows": 0, "rows_used": 0,
          "sample_pct": C.CUSTOMER_SAMPLE_PCT}
    props = read_all("product_properties", [C.COL_SKU, C.COL_PRICE]).drop_duplicates(C.COL_SKU)
    price = props.set_index(C.COL_SKU)[C.COL_PRICE]
    tables = {}
    for col, name in EVENTS.items():
        parts, vparts = [], []
        extra = [C.COL_SKU] if name == "product_buy" else []
        for ch in iter_chunks(name, [C.COL_CLIENT, C.COL_TS] + extra):
            ch = clean_chunk(ch, qa)
            g = ch.groupby([C.COL_CLIENT, "date"])
            parts.append(g.size().rename(col))
            if name == "product_buy":                 # relative value: quantised price bucket of purchased items
                ch = ch.assign(v=ch[C.COL_SKU].map(price).fillna(0))
                vparts.append(ch.groupby([C.COL_CLIENT, "date"])["v"].sum().rename("buy_value"))
        tables[col] = pd.concat(parts).groupby(level=[0, 1]).sum()
        if vparts:
            tables["buy_value"] = pd.concat(vparts).groupby(level=[0, 1]).sum()
        print(f"  {name}: {len(tables[col]):,} customer-days")
    df = pd.concat(tables.values(), axis=1).fillna(0)
    df.index.names = ["customer_id", "date"]
    df = df.reset_index()
    for c in ["visits", "searches", "carts", "removes", "buys"]:
        df[c] = df[c].astype(int)
    df["events"] = df[["visits", "searches", "carts", "removes", "buys"]].sum(axis=1)
    df["buy_value"] = df["buy_value"].astype(float)
    df = df.sort_values(["customer_id", "date"])
    assert not df.duplicated(["customer_id", "date"]).any()
    df.to_csv(activity_path(), index=False)
    qa.update(customers=int(df["customer_id"].nunique()), customer_days=len(df),
              date_from=str(df["date"].min().date()), date_to=str(df["date"].max().date()))
    (C.TABLES / "data_quality.json").write_text(json.dumps(qa, indent=2))
    print("saved", activity_path(), qa)


if __name__ == "__main__":
    build()
