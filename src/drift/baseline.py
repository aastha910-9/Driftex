"""One rolling PERSONAL baseline per customer, computed from past observations only (Shaffy)."""
import numpy as np


def rolling_baseline(X, first, window=28, min_obs=14):
    """
    X     : customers x days daily activity (events per day)
    first : index of each customer's first active day (days before it are NOT part of the baseline)
    Returns mu, sd with shape of X. mu[:, t], sd[:, t] use days [max(t-window, first), t-1] ONLY (never day t or later).
    NaN where fewer than `min_obs` past days exist (insufficient history).
    """
    C, D = X.shape
    cs = np.concatenate([np.zeros((C, 1)), np.cumsum(X, axis=1, dtype=np.float64)], axis=1)
    cs2 = np.concatenate([np.zeros((C, 1)), np.cumsum(X.astype(np.float64) ** 2, axis=1)], axis=1)
    t = np.arange(D)[None, :]
    lo = np.maximum(t - window, first[:, None])
    lo = np.minimum(lo, t)
    n = (t - lo).astype(np.float64)
    hi_idx = np.broadcast_to(t, (C, D))
    s = np.take_along_axis(cs, hi_idx, axis=1) - np.take_along_axis(cs, lo, axis=1)
    s2 = np.take_along_axis(cs2, hi_idx, axis=1) - np.take_along_axis(cs2, lo, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = s / n
        sd = np.sqrt(np.maximum(s2 / n - mu ** 2, 0))
    bad = n < min_obs
    mu[bad] = np.nan
    sd[bad] = np.nan
    return mu.astype(np.float32), sd.astype(np.float32)
