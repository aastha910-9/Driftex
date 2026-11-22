"""Historical customer value PROXY (Shaffy) - NOT predicted lifetime value.
Formula: historical_value_proxy = sum over the customer's purchases of the product's `price` field.
In the Synerise data `price` is a quantised price BUCKET (0-99), not currency, so the proxy is a relative
purchase-value index. Written only if purchases and price data exist."""
import pandas as pd
from src.common import C, load_activity

FORMULA = "sum(price_bucket of purchased products); relative index, not currency, not predicted CLV"


def compute_value(act):
    g = act.groupby("customer_id")
    v = pd.DataFrame({"historical_value_proxy": g["buy_value"].sum(), "purchases": g["buys"].sum()})
    v["value_percentile"] = v["historical_value_proxy"].rank(pct=True).round(3)
    v["value_tier"] = pd.cut(v["value_percentile"], [0, .5, .8, 1.0], labels=["Standard", "High", "Top 20%"], include_lowest=True)
    v["formula"] = FORMULA
    return v


def main():
    act = load_activity()
    if "buy_value" not in act or act["buy_value"].sum() <= 0:
        print("No reliable value data -> customer_value.csv NOT created (documented limitation).")
        return
    v = compute_value(act)
    v.reset_index().to_csv(C.OUT_DIR / "customer_value.csv", index=False)
    print(f"customer_value.csv: {len(v):,} customers | customers without purchases: {(v.purchases == 0).mean():.1%}")


if __name__ == "__main__":
    main()
