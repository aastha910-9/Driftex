import numpy as np
import pandas as pd
from src.insights.segments import SEG_FEATURES, prepare, fit_segments


def _table(n=300):
    rng = np.random.default_rng(1)
    hi = pd.DataFrame({f: rng.poisson(50, n // 2) for f in SEG_FEATURES}); lo = pd.DataFrame({f: rng.poisson(2, n // 2) for f in SEG_FEATURES})
    return pd.concat([hi, lo], ignore_index=True).astype(float)


def test_inputs_are_scaled_and_finite():
    X = prepare(_table())
    assert np.isfinite(X).all() and np.allclose(X.mean(0), 0, atol=1e-6) and np.allclose(X.std(0), 1, atol=1e-6)


def test_kmeans_separates_two_obvious_groups():
    lab, k, sil = fit_segments(_table(), ks=(2, 3))
    assert k == 2 and sil > 0.5 and len(set(lab[:150])) == 1 and set(lab[:150]) != set(lab[150:])


def test_value_proxy_output():
    from src.insights.value_proxy import compute_value
    act = pd.DataFrame({"customer_id": [1, 1, 2, 3], "buy_value": [10.0, 5.0, 40.0, 0.0], "buys": [1, 1, 2, 0]})
    v = compute_value(act)
    assert v.loc[1, "historical_value_proxy"] == 15 and v.loc[2, "historical_value_proxy"] == 40
    assert v["value_percentile"].between(0, 1).all() and v.loc[2, "value_percentile"] == 1.0 and (v["formula"].str.len() > 0).all()
