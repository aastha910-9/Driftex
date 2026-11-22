import numpy as np
import pandas as pd
from src.prediction.labels import make_labels
from src.prediction.evaluate import evaluate
from src.prediction.train import build_pipeline, chronological_split, FEATURE_SETS
from src.common import cumsum0, window_sum


def test_label_boundaries():
    ev = np.zeros((2, 100), dtype=np.float32)
    ev[0, 40] = 1                      # activity exactly on t+30 -> NOT inactive
    ev[1, 41] = 1                      # activity one day after the window -> inactive
    valid, Y = make_labels(ev, np.array([10]), 30)
    assert Y[0, 0] == 0 and Y[1, 0] == 1
    ev[0, 10] = 1                      # activity ON day t is not part of (t, t+30]
    _, Y = make_labels(ev, np.array([10]), 30)
    assert Y[0, 0] == 0                # still active at day 40
    ev[0, 40] = 0
    _, Y = make_labels(ev, np.array([10]), 30)
    assert Y[0, 0] == 1


def test_incomplete_followup_excluded():
    ev = np.ones((1, 100), dtype=np.float32)
    valid, _ = make_labels(ev, np.array([10, 69, 70, 71, 99]), 30)
    assert list(valid) == [10, 69]                # t+30 must be <= last day (99): t=70 would need day 100


def test_features_use_past_only():
    ev = np.random.default_rng(0).poisson(1, (3, 80)).astype(np.float32)
    f1 = window_sum(cumsum0(ev), 40, 28)
    ev2 = ev.copy(); ev2[:, 41:] += 50
    assert np.allclose(f1, window_sum(cumsum0(ev2), 40, 28))


def test_chronological_split_has_gap():
    d = pd.date_range("2022-01-01", periods=60, freq="7D")
    tr_end, te_start = chronological_split(d, 0.25, 30)
    assert te_start - tr_end == pd.Timedelta(days=30) and tr_end < te_start


def test_scaler_fit_on_train_only_and_models_train():
    rng = np.random.default_rng(0)
    cols = FEATURE_SETS["conventional"]
    tr = pd.DataFrame(rng.normal(0, 1, (400, len(cols))), columns=cols); y = (tr[cols[0]] + rng.normal(0, .5, 400) > 0.5).astype(int)
    te = pd.DataFrame(rng.normal(100, 1, (50, len(cols))), columns=cols)
    for name in ["Logistic Regression", "Random Forest"]:
        pipe = build_pipeline(name, cols, 1.0).fit(tr, y)
        sc = pipe.named_steps["pre"].named_transformers_["num"].named_steps["sc"]
        assert abs(sc.mean_[0]) < 0.3                 # statistics come from the TRAIN data, not the shifted test data
        assert pipe.predict_proba(te).shape == (50, 2)


def test_metrics_keys_and_single_class():
    m = evaluate([0, 1, 1, 0], [0.1, 0.9, 0.6, 0.4])
    assert {"Precision", "Recall", "F1", "PR_AUC", "ROC_AUC"} <= set(m) and m["ROC_AUC"] == 1.0
    assert np.isnan(evaluate([0, 0, 0], [0.1, 0.2, 0.3])["ROC_AUC"])      # ROC-AUC not valid with one class
