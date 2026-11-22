"""Runs the full drift pipeline and exports data/processed/drift_features.csv (Shaffy).
   python -m src.drift.run_drift [--build]    (--build re-creates customer_daily_activity.csv first)"""
import sys
import numpy as np
import pandas as pd
from src.common import C, Panel, load_activity, obs_indices, activity_path
from src.drift.detect import compute_drift


def main():
    if "--build" in sys.argv or not activity_path().exists():
        from src.drift.activity import build
        build()
    df = load_activity()
    P = Panel(df, ["events"])
    r = compute_drift(P.M["events"], P.first, C.BASELINE_DAYS, C.MIN_HISTORY_DAYS, C.CUSTOMER_EWMA_SPAN,
                      C.DRIFT_EWMA_THRESH, C.PERSIST_DAYS, C.SD_FLOOR)
    rows = []
    for t in obs_indices(P.D, C.OBS_STEP_DAYS):
        ok = ~np.isnan(r["z"][:, t])
        rows.append(pd.DataFrame({
            "customer_id": P.customers[ok], "date": P.days[t].date(),
            "drift_zscore": r["z"][ok, t].round(3), "drift_ewma": r["ewma"][ok, t].round(3),
            "drift_flag": r["flag"][ok, t], "drift_level": np.abs(r["ewma"][ok, t]).round(3),
            "drift_direction": r["direction"][ok, t], "drift_run_days": r["run"][ok, t]}))
    out = pd.concat(rows)
    out.to_csv(C.OUT_DIR / "drift_features.csv", index=False)
    print(f"drift_features.csv: {len(out):,} rows | customers {out.customer_id.nunique():,} | "
          f"sustained-decline share {(out.drift_direction < 0).mean():.1%}")


if __name__ == "__main__":
    main()
