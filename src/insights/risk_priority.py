"""Risk prioritisation (shared). Rule:  priority_score = predicted_inactivity_probability x value_percentile.
If value data is unavailable the ranking uses probability only. Uses the NEWEST observation date (no label needed)."""
import pandas as pd
from src.common import C


def main():
    sc = pd.read_csv(C.OUT_DIR / "scoring_predictions.csv")
    vpath = C.OUT_DIR / "customer_value.csv"
    if vpath.exists():
        v = pd.read_csv(vpath)[["customer_id", "historical_value_proxy", "value_percentile", "value_tier"]]
        sc = sc.merge(v, on="customer_id", how="left")
        sc["value_percentile"] = sc["value_percentile"].fillna(0)
        sc["priority_score"] = (sc["predicted_probability"] * sc["value_percentile"]).round(4)
        rule = "predicted_probability x value_percentile"
    else:
        sc["priority_score"] = sc["predicted_probability"]; rule = "predicted_probability only (no value data)"
    seg = C.OUT_DIR / "customer_segments.csv"
    if seg.exists():
        sc = sc.merge(pd.read_csv(seg)[["customer_id", "segment_name"]], on="customer_id", how="left")
    sc = sc.sort_values("priority_score", ascending=False)
    sc["priority_rank"] = range(1, len(sc) + 1)
    sc["action_tier"] = pd.qcut(sc["priority_rank"], [0, .05, .2, 1.0], labels=["Act now", "Monitor closely", "Routine"])
    sc.to_csv(C.OUT_DIR / "risk_priority.csv", index=False)
    print(f"risk_priority.csv: {len(sc):,} customers | rule: {rule}")


if __name__ == "__main__":
    main()
