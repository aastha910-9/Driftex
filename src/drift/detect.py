"""Z-score, EWMA and a persistence rule for behavioural drift warnings (Shaffy)."""
import numpy as np


def zscore(X, mu, sd, sd_floor=0.5, clip=5.0):
    """Deviation of today's activity from the customer's own past baseline."""
    return np.clip((X - mu) / (sd + sd_floor), -clip, clip)


def ewma(Z, span=7):
    """Exponentially weighted moving average along days; starts at the first valid z."""
    a = 2.0 / (span + 1)
    out = np.full_like(Z, np.nan, dtype=np.float32)
    prev = np.full(Z.shape[0], np.nan, dtype=np.float32)
    for t in range(Z.shape[1]):
        z = Z[:, t]
        cur = np.where(np.isnan(prev), z, a * z + (1 - a) * prev)
        cur = np.where(np.isnan(z), prev, cur)
        out[:, t] = cur
        prev = cur
    return out


def persistence(E, thresh=0.5, k=5):
    """
    drift_flag = 1 when |EWMA| stays beyond `thresh` in the SAME direction for >= k consecutive days.
    direction  = -1 sustained decline, +1 sustained increase, 0 none.   run = current streak length.
    """
    dec = np.nan_to_num(E, nan=0.0) <= -thresh
    inc = np.nan_to_num(E, nan=0.0) >= thresh
    rd = np.zeros(E.shape, dtype=np.int16); ri = np.zeros(E.shape, dtype=np.int16)
    pd_, pi_ = np.zeros(E.shape[0], dtype=np.int16), np.zeros(E.shape[0], dtype=np.int16)
    for t in range(E.shape[1]):
        pd_ = (pd_ + 1) * dec[:, t]; pi_ = (pi_ + 1) * inc[:, t]
        rd[:, t], ri[:, t] = pd_, pi_
    flag_dec, flag_inc = rd >= k, ri >= k
    direction = np.where(flag_dec, -1, np.where(flag_inc, 1, 0)).astype(np.int8)
    run = np.where(flag_dec, rd, np.where(flag_inc, ri, np.maximum(rd, ri))).astype(np.int16)
    return (direction != 0).astype(np.int8), direction, run


def compute_drift(X, first, window=28, min_obs=14, span=7, thresh=0.5, k=5, sd_floor=0.5):
    from src.drift.baseline import rolling_baseline
    mu, sd = rolling_baseline(X, first, window, min_obs)
    Z = zscore(X, mu, sd, sd_floor)
    E = ewma(Z, span)
    flag, direction, run = persistence(E, thresh, k)
    return dict(mu=mu, sd=sd, z=Z, ewma=E, flag=flag, direction=direction, run=run)
