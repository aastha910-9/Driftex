"""Conventional past-only predictors (Aastha). Every feature at observation day t uses days <= t only."""
import numpy as np
import pandas as pd
from src.common import C, Panel, load_activity, obs_indices, cumsum0, window_sum, eligible_mask

CONV_FEATURES = ["events_7d", "events_14d", "events_28d", "active_days_7d", "active_days_28d", "visits_28d",
                 "searches_28d", "carts_28d", "removes_28d", "buys_28d", "days_since_last", "tenure_days",
                 "trend_7_vs_28", "cart_to_buy_28d"]


def build_features(P, obs_idx):
    cs = {m: cumsum0(P.M[m]) for m in ["events", "visits", "searches", "carts", "removes", "buys"]}
    csa = cumsum0(P.active.astype(np.float32))
    idx = np.arange(P.D)[None, :]
    last_active = np.maximum.accumulate(np.where(P.active, idx, -1), axis=1)   # latest active day <= t
    rows = []
    for t in obs_idx:
        m = eligible_mask(P, t)
        if not m.any():
            continue
        e7, e14, e28 = (window_sum(cs["events"], t, w)[m] for w in (7, 14, 28))
        c28, b28 = window_sum(cs["carts"], t, 28)[m], window_sum(cs["buys"], t, 28)[m]
        rows.append(pd.DataFrame({
            "customer_id": P.customers[m], "observation_date": P.days[t].date(),
            "events_7d": e7, "events_14d": e14, "events_28d": e28,
            "active_days_7d": window_sum(csa, t, 7)[m], "active_days_28d": window_sum(csa, t, 28)[m],
            "visits_28d": window_sum(cs["visits"], t, 28)[m], "searches_28d": window_sum(cs["searches"], t, 28)[m],
            "carts_28d": c28, "removes_28d": window_sum(cs["removes"], t, 28)[m], "buys_28d": b28,
            "days_since_last": t - last_active[m, t], "tenure_days": t - P.first[m],
            "trend_7_vs_28": e7 / (e28 / 4.0 + 1.0), "cart_to_buy_28d": b28 / (c28 + 1.0)}))
    return pd.concat(rows, ignore_index=True)


def main():
    P = Panel(load_activity(), ["events", "visits", "searches", "carts", "removes", "buys"])
    out = build_features(P, obs_indices(P.D, C.OBS_STEP_DAYS))
    out.to_csv(C.OUT_DIR / "model_features.csv", index=False)
    print(f"model_features.csv: {len(out):,} rows | {len(CONV_FEATURES)} past-only predictors")


if __name__ == "__main__":
    main()
