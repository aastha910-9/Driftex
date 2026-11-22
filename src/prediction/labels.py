"""30-day inactivity labels (Aastha).  inactive_30d = 1  <=>  NO qualifying activity in (t, t + 30 days].
Observations without a complete future 30-day window are excluded."""
import numpy as np
import pandas as pd
from src.common import C, Panel, load_activity, obs_indices, cumsum0, eligible_mask


def make_labels(events, obs_idx, horizon=30):
    """events: customers x days matrix. Returns (valid_obs_idx, label matrix customers x len(valid))."""
    D = events.shape[1]
    valid = np.array([t for t in obs_idx if t + horizon <= D - 1], dtype=int)   # full window must exist in the data
    cs = cumsum0(events)
    fut = cs[:, valid + horizon + 1] - cs[:, valid + 1]                         # events on days t+1 .. t+horizon
    return valid, (fut == 0).astype(np.int8)


def main():
    P = Panel(load_activity(), ["events"])
    obs = obs_indices(P.D, C.OBS_STEP_DAYS)
    valid, Y = make_labels(P.M["events"], obs, C.INACTIVITY_HORIZON)
    rows = []
    for j, t in enumerate(valid):
        m = eligible_mask(P, t)                                 # same eligible population as the features
        rows.append(pd.DataFrame({"customer_id": P.customers[m], "observation_date": P.days[t].date(),
                                  "inactive_30d": Y[m, j]}))
    out = pd.concat(rows)
    out.to_csv(C.OUT_DIR / "inactivity_labels.csv", index=False)
    print(f"inactivity_labels.csv: {len(out):,} rows | positive (inactive) rate {out.inactive_30d.mean():.1%} "
          f"| excluded last {C.INACTIVITY_HORIZON} days (incomplete follow-up)")


if __name__ == "__main__":
    main()
