"""
STEP 1 - Data integration.
Reads the six Synerise files chunk by chunk and writes three small tables:
  processed/daily_company.csv  : date x (visits, searches, carts, removes, buys, cart_users, buyers)
  processed/daily_product.csv  : date x sku x (views, carts, removes, buys)
  processed/products.csv       : sku -> category, price
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parent))
import config as C
from io_utils import iter_chunks, columns_of, read_all, day_of


def product_events(name):
    """-> (daily per-sku counts, daily company counts, daily unique clients)"""
    cols = [C.COL_CLIENT, C.COL_TS, C.COL_SKU]
    per_sku, per_client = [], []
    for ch in iter_chunks(name, cols):
        ch["day"] = day_of(ch[C.COL_TS])
        per_sku.append(ch.groupby(["day", C.COL_SKU]).size().rename("n").reset_index())
        per_client.append(ch[["day", C.COL_CLIENT]].drop_duplicates())
    sku = pd.concat(per_sku).groupby(["day", C.COL_SKU], as_index=False)["n"].sum()
    clients = (pd.concat(per_client).drop_duplicates().groupby("day").size().rename("users"))
    return sku, clients


def page_visits():
    cols = columns_of("page_visit")
    sku_col = C.PAGE_VISIT_SKU_COL or (C.COL_SKU if C.COL_SKU in cols else None)
    use = [C.COL_TS] + ([sku_col] if sku_col else [])
    company, per_sku = [], []
    for ch in iter_chunks("page_visit", use):
        ch["day"] = day_of(ch[C.COL_TS])
        company.append(ch.groupby("day").size().rename("n").reset_index())
        if sku_col:
            per_sku.append(ch.groupby(["day", sku_col]).size().rename("n").reset_index()
                           .rename(columns={sku_col: C.COL_SKU}))
    company = pd.concat(company).groupby("day")["n"].sum()
    sku = pd.concat(per_sku).groupby(["day", C.COL_SKU], as_index=False)["n"].sum() if per_sku else None
    return company, sku


def main():
    print("[1/6] add_to_cart");        cart, cart_u = product_events("add_to_cart")
    print("[2/6] remove_from_cart");   rem, _ = product_events("remove_from_cart")
    print("[3/6] product_buy");        buy, buy_u = product_events("product_buy")
    print("[4/6] page_visit (large)"); pv_company, pv_sku = page_visits()
    print("[5/6] search_query")
    sq = pd.concat([day_of(c[C.COL_TS]).value_counts().rename_axis("day").rename("n")
                    for c in iter_chunks("search_query", [C.COL_TS])]).groupby(level=0).sum()
    print("[6/6] product_properties")
    props = read_all("product_properties", [C.COL_SKU, C.COL_CATEGORY, C.COL_PRICE])
    props.to_csv(C.OUT_DIR / "products.csv", index=False)

    # ---- product x day
    frames = {"carts": cart, "removes": rem, "buys": buy}
    if pv_sku is not None:
        frames["views"] = pv_sku
    dp = None
    for k, f in frames.items():
        f = f.rename(columns={"n": k})
        dp = f if dp is None else dp.merge(f, on=["day", C.COL_SKU], how="outer")
    for k in ["views", "carts", "removes", "buys"]:
        if k not in dp: dp[k] = 0
    dp = dp.fillna(0).rename(columns={"day": "date", C.COL_SKU: "sku"})
    dp[["views", "carts", "removes", "buys"]] = dp[["views", "carts", "removes", "buys"]].astype(int)
    dp.sort_values(["sku", "date"]).to_csv(C.OUT_DIR / "daily_product.csv", index=False)

    # ---- company x day
    comp = pd.DataFrame({
        "visits": pv_company, "searches": sq,
        "carts": cart.groupby("day")["n"].sum(), "removes": rem.groupby("day")["n"].sum(),
        "buys": buy.groupby("day")["n"].sum(), "cart_users": cart_u, "buyers": buy_u}).fillna(0).astype(int)
    comp.index.name = "date"
    comp.reset_index().to_csv(C.OUT_DIR / "daily_company.csv", index=False)
    meta = {"has_product_views": pv_sku is not None}
    import json; (C.OUT_DIR / "meta.json").write_text(json.dumps(meta))
    print("done ->", C.OUT_DIR, "| product-level page views:", meta["has_product_views"])


if __name__ == "__main__":
    main()
