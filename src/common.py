"""Shared helpers: paths, loading the customer-day table and turning it into dense matrices."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "pipeline"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import config as C  # noqa: E402

MEASURES = ["events", "visits", "searches", "carts", "removes", "buys", "buy_value"]


def activity_path():
    return C.OUT_DIR / "customer_daily_activity.csv"


def load_activity():
    df = pd.read_csv(activity_path(), parse_dates=["date"])
    return df


class Panel:
    """Customers x days dense matrices (0 on days without activity)."""

    def __init__(self, df, measures=("events",)):
        self.customers = np.sort(df["customer_id"].unique())
        self.day0 = df["date"].min()
        self.D = int((df["date"].max() - self.day0).days) + 1
        self.days = pd.date_range(self.day0, periods=self.D)
        ci = np.searchsorted(self.customers, df["customer_id"].values)
        di = (df["date"] - self.day0).dt.days.values
        self.M = {}
        for m in measures:
            a = np.zeros((len(self.customers), self.D), dtype=np.float32)
            a[ci, di] = df[m].values
            self.M[m] = a
        act = np.zeros((len(self.customers), self.D), dtype=bool)
        act[ci, di] = df["events"].values > 0
        self.active = act
        first = np.where(act.any(1), act.argmax(1), self.D)
        self.first = first                       # index of first active day per customer


def obs_indices(D, step, min_idx=0):
    """Observation day indices, anchored on the LAST day so the newest day is always scored."""
    idx = np.arange(D - 1, -1, -step)[::-1]
    return idx[idx >= min_idx]


def cumsum0(M):
    """cs[:, k] = sum of M[:, :k]  (so any window sum is a difference of two columns)."""
    return np.concatenate([np.zeros((M.shape[0], 1), dtype=np.float64), np.cumsum(M, axis=1, dtype=np.float64)], axis=1)


def window_sum(cs, t, w):
    """Sum of days (t-w, t] for every customer, using only days <= t."""
    lo = max(t + 1 - w, 0)
    return cs[:, t + 1] - cs[:, lo]


def eligible_mask(panel, t):
    """Eligible at observation day t: enough history AND active at least once in the last RECENT_ACTIVE_DAYS."""
    hist = (t - panel.first) >= C.MIN_HISTORY_DAYS
    lo = max(t + 1 - C.RECENT_ACTIVE_DAYS, 0)
    recent = panel.active[:, lo:t + 1].any(1)
    return hist & recent
