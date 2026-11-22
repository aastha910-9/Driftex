import numpy as np
from src.drift.baseline import rolling_baseline
from src.drift.detect import zscore, ewma, persistence, compute_drift


def _x(seed=0, C=5, D=80):
    return np.random.default_rng(seed).poisson(1.5, (C, D)).astype(np.float32), np.zeros(C, dtype=int)


def test_baseline_never_uses_future():
    X, first = _x()
    mu1, sd1 = rolling_baseline(X, first)
    X2 = X.copy(); X2[:, 50:] += 100                         # change the future
    mu2, sd2 = rolling_baseline(X2, first)
    assert np.allclose(mu1[:, :51], mu2[:, :51], equal_nan=True)   # baseline at t<=50 only sees days < t
    assert np.allclose(sd1[:, :51], sd2[:, :51], equal_nan=True)


def test_baseline_value_and_insufficient_history():
    X = np.ones((1, 40), dtype=np.float32); first = np.array([0])
    mu, sd = rolling_baseline(X, first, window=28, min_obs=14)
    assert np.isnan(mu[0, :14]).all() and not np.isnan(mu[0, 14:]).any()   # <14 past days -> NaN
    assert np.allclose(mu[0, 14:], 1.0) and np.allclose(sd[0, 14:], 0.0)


def test_baseline_ignores_days_before_first_activity():
    X = np.zeros((1, 60), dtype=np.float32); X[0, 30:] = 2; first = np.array([30])
    mu, _ = rolling_baseline(X, first, window=28, min_obs=14)
    assert np.isnan(mu[0, :44]).all() and np.allclose(mu[0, 44:], 2.0)


def test_zscore_sign_and_clip():
    z = zscore(np.array([[0.0, 100.0]]), np.array([[2.0, 2.0]]), np.array([[1.0, 1.0]]))
    assert z[0, 0] < 0 and z[0, 1] == 5.0


def test_ewma_smooths_and_keeps_nan_start():
    Z = np.array([[np.nan, 1.0, 1.0, -1.0]], dtype=np.float32)
    E = ewma(Z, span=3)
    assert np.isnan(E[0, 0]) and E[0, 1] == 1.0 and -1 < E[0, 3] < 1


def test_persistence_needs_consecutive_days():
    E = np.array([[-1, -1, -1, -1, 0, -1, -1, -1, -1, -1]], dtype=np.float32)
    flag, direction, run = persistence(E, thresh=0.5, k=5)
    assert flag[0, :9].sum() == 0 and flag[0, 9] == 1 and direction[0, 9] == -1 and run[0, 9] == 5


def test_decline_detected_for_fading_customer():
    X = np.concatenate([np.full(40, 3.0), np.zeros(20)])[None, :].astype(np.float32)
    r = compute_drift(X, np.array([0]))
    assert r["direction"][0, -1] == -1
