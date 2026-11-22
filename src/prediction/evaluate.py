"""Metrics and warning-lead-time evaluation (Aastha). Positive class = inactive_30d = 1."""
import numpy as np
import pandas as pd
from sklearn.metrics import (precision_score, recall_score, f1_score, average_precision_score,
                             roc_auc_score)


def evaluate(y, p, threshold=0.5):
    y, p = np.asarray(y), np.asarray(p)
    pred = (p >= threshold).astype(int)
    both = len(np.unique(y)) == 2
    return {"Precision": precision_score(y, pred, zero_division=0), "Recall": recall_score(y, pred, zero_division=0),
            "F1": f1_score(y, pred, zero_division=0),
            "PR_AUC": average_precision_score(y, p) if both else np.nan,
            "ROC_AUC": roc_auc_score(y, p) if both else np.nan,
            "positive_rate": float(y.mean()), "threshold": threshold, "n": int(len(y))}


def warning_lead_time(activity, drift, horizon=30, lookback=60):
    """
    Defensible definition: for customers whose LAST activity day L is followed by >= `horizon` silent days inside
    the data, the conventional rule ("30 days without activity") fires at L + horizon.
    The drift warning fires at the first sustained-DECLINE flag within [L - lookback, L + horizon].
    lead_time = (L + horizon) - warning_date  (days).  Resolution = observation grid (OBS_STEP_DAYS).
    """
    last_day = activity["date"].max()
    L = activity.groupby("customer_id")["date"].max()
    L = L[L + pd.Timedelta(days=horizon) <= last_day]
    d = drift[drift["drift_direction"] < 0].copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.merge(L.rename("L"), left_on="customer_id", right_index=True)
    d = d[(d["date"] >= d["L"] - pd.Timedelta(days=lookback)) & (d["date"] <= d["L"] + pd.Timedelta(days=horizon))]
    w = d.groupby("customer_id")["date"].min()
    lead = ((L.loc[w.index] + pd.Timedelta(days=horizon)) - w).dt.days
    return {"customers_with_inactivity_episode": int(len(L)), "customers_warned": int(len(w)),
            "share_warned": float(len(w) / max(len(L), 1)), "median_lead_days": float(lead.median()) if len(lead) else np.nan,
            "mean_lead_days": float(lead.mean()) if len(lead) else np.nan}
