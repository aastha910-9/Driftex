"""Train Logistic Regression, Random Forest and XGBoost in ONE pipeline (Aastha) and compare
conventional vs drift-enhanced feature sets on identical chronological test observations.
   python -m src.prediction.train"""
import json
import numpy as np
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from src.common import C
from src.prediction.features import CONV_FEATURES
from src.prediction.evaluate import evaluate, warning_lead_time

DRIFT_FEATURES = ["drift_zscore", "drift_ewma", "drift_flag", "drift_level", "drift_run_days"]
FEATURE_SETS = {"conventional": CONV_FEATURES, "drift_enhanced": CONV_FEATURES + DRIFT_FEATURES}


def make_model(name, pos_weight=1.0):
    if name == "Logistic Regression":
        return LogisticRegression(max_iter=2000, class_weight="balanced")
    if name == "Random Forest":
        return RandomForestClassifier(n_estimators=250, min_samples_leaf=20, class_weight="balanced_subsample",
                                      n_jobs=-1, random_state=C.RANDOM_STATE)
    if name == "XGBoost":
        from xgboost import XGBClassifier
        return XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.06, subsample=0.85, colsample_bytree=0.85,
                             scale_pos_weight=pos_weight, eval_metric="logloss", random_state=C.RANDOM_STATE, n_jobs=-1)
    raise ValueError(name)


def build_pipeline(name, cols, pos_weight):
    """Imputation + scaling live INSIDE the pipeline so they are fitted on training rows only."""
    pre = ColumnTransformer([("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), cols)])
    return Pipeline([("pre", pre), ("clf", make_model(name, pos_weight))])


def chronological_split(dates, test_fraction, gap_days):
    """Test = last `test_fraction` of observation dates. Training dates end `gap_days` before the test start so no
    training label window (t, t+30] overlaps the test period."""
    u = pd.DatetimeIndex(np.sort(pd.to_datetime(pd.Series(dates).unique())))
    start = u[int(len(u) * (1 - test_fraction))]
    train_end = start - pd.Timedelta(days=gap_days)
    return train_end, start


def load_dataset():
    X = pd.read_csv(C.OUT_DIR / "model_features.csv", parse_dates=["observation_date"])
    y = pd.read_csv(C.OUT_DIR / "inactivity_labels.csv", parse_dates=["observation_date"])
    d = pd.read_csv(C.OUT_DIR / "drift_features.csv", parse_dates=["date"]).rename(columns={"date": "observation_date"})
    full = X.merge(d[["customer_id", "observation_date"] + DRIFT_FEATURES], on=["customer_id", "observation_date"], how="inner")
    return full, y


def main():
    full, labels = load_dataset()
    data = full.merge(labels, on=["customer_id", "observation_date"], how="inner")     # labelled rows only
    train_end, test_start = chronological_split(data["observation_date"], C.TEST_FRACTION, C.INACTIVITY_HORIZON)
    tr, te = data[data["observation_date"] <= train_end], data[data["observation_date"] >= test_start]
    print(f"rows {len(data):,} | train <= {train_end.date()} ({len(tr):,}) | test >= {test_start.date()} ({len(te):,}) "
          f"| inactive rate train {tr.inactive_30d.mean():.1%} test {te.inactive_30d.mean():.1%}")
    pos_w = (1 - tr.inactive_30d.mean()) / max(tr.inactive_30d.mean(), 1e-6)
    names = ["Logistic Regression", "Random Forest"]
    try:
        import xgboost  # noqa: F401
        names.append("XGBoost")
    except ImportError:
        print("WARNING: xgboost not installed -> skipped (pip install xgboost)")
    metrics, preds, fitted = [], [], {}
    for fs, cols in FEATURE_SETS.items():
        for n in names:
            pipe = build_pipeline(n, cols, pos_w).fit(tr[cols], tr["inactive_30d"])
            p = pipe.predict_proba(te[cols])[:, 1]
            metrics.append({"model_name": n, "feature_set": fs, "split": "test", **evaluate(te["inactive_30d"], p, C.DECISION_THRESHOLD)})
            preds.append(pd.DataFrame({"customer_id": te["customer_id"].values, "observation_date": te["observation_date"].dt.date.values,
                                       "model_name": n, "feature_set": fs, "inactive_30d": te["inactive_30d"].values,
                                       "predicted_probability": p.round(4), "predicted_class": (p >= C.DECISION_THRESHOLD).astype(int)}))
            fitted[(n, fs)] = pipe
            joblib.dump(pipe, C.MODELS / f"{n.replace(' ', '_')}__{fs}.joblib")
            print(f"  {fs:15s} {n:20s} PR-AUC {metrics[-1]['PR_AUC']:.3f}  ROC-AUC {metrics[-1]['ROC_AUC']:.3f}  F1 {metrics[-1]['F1']:.3f}")
    M = pd.DataFrame(metrics)
    M.to_csv(C.OUT_DIR / "model_metrics.csv", index=False); M.to_csv(C.TABLES / "model_metrics.csv", index=False)
    pd.concat(preds).to_csv(C.OUT_DIR / "predictions.csv", index=False)

    # model chosen for explanation / scoring = best PR-AUC among drift-enhanced models (fixed rule, reported as-is)
    best = M[M.feature_set == "drift_enhanced"].sort_values("PR_AUC", ascending=False).iloc[0]["model_name"]
    pipe, cols = fitted[(best, "drift_enhanced")], FEATURE_SETS["drift_enhanced"]
    latest = full[full["observation_date"] == full["observation_date"].max()]          # newest day: no label needed
    sc = latest[["customer_id", "observation_date"]].copy()
    sc["predicted_probability"] = pipe.predict_proba(latest[cols])[:, 1].round(4)
    sc["predicted_class"] = (sc["predicted_probability"] >= C.DECISION_THRESHOLD).astype(int)
    sc["model_name"] = best
    sc.to_csv(C.OUT_DIR / "scoring_predictions.csv", index=False)

    # warning lead time (drift warning vs the conventional "30 days silent" rule)
    act = pd.read_csv(C.OUT_DIR / "customer_daily_activity.csv", parse_dates=["date"], usecols=["customer_id", "date"])
    drift = pd.read_csv(C.OUT_DIR / "drift_features.csv")
    lead = warning_lead_time(act, drift, C.INACTIVITY_HORIZON)
    info = {"best_drift_enhanced_model": best, "train_end": str(train_end.date()), "test_start": str(test_start.date()),
            "n_train": len(tr), "n_test": len(te), "threshold": C.DECISION_THRESHOLD, "positive_class": "inactive_30d = 1",
            "warning_lead_time": lead}
    (C.TABLES / "experiment_summary.json").write_text(json.dumps(info, indent=2, default=float))
    print("best drift-enhanced model:", best, "| lead time:", lead)


if __name__ == "__main__":
    main()
