"""K-Means engagement segmentation (Shaffy). Small documented feature set, log-transformed and scaled."""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from src.common import C, load_activity

SEG_FEATURES = ["active_days", "events_per_active_day", "buys_total", "carts_total", "searches_total", "recency_days"]
NAMES = ["Highly engaged", "Regular", "Occasional", "Low activity", "Fading", "Dormant"]


def customer_table(act):
    end = act["date"].max()
    g = act.groupby("customer_id")
    t = pd.DataFrame({"active_days": g.size(), "events_total": g["events"].sum(), "buys_total": g["buys"].sum(),
                      "carts_total": g["carts"].sum(), "searches_total": g["searches"].sum(),
                      "recency_days": (end - g["date"].max()).dt.days})
    t["events_per_active_day"] = t["events_total"] / t["active_days"]
    return t


def prepare(t):
    """log1p for count-like features, then standard scaling (K-Means is distance based)."""
    X = np.log1p(t[SEG_FEATURES].astype(float).clip(lower=0))
    return StandardScaler().fit_transform(X)


def fit_segments(t, ks=C.KMEANS_K_RANGE, seed=C.RANDOM_STATE):
    X = prepare(t)
    sub = np.random.default_rng(seed).choice(len(X), min(len(X), 8000), replace=False)
    best_k, best_s = None, -1
    for k in ks:
        lab = KMeans(k, n_init=5, random_state=seed).fit_predict(X[sub])
        s = silhouette_score(X[sub], lab)
        if s > best_s: best_k, best_s = k, s
    km = KMeans(best_k, n_init=10, random_state=seed).fit(X)
    return km.labels_, best_k, best_s


def main():
    act = load_activity()
    t = customer_table(act)
    lab, k, sil = fit_segments(t)
    t["segment_id"] = lab
    order = t.groupby("segment_id")["events_total"].mean().sort_values(ascending=False).index.tolist()
    rec = t.groupby("segment_id")["recency_days"].mean()
    nm = {sid: NAMES[i] + (" (lapsing)" if rec[sid] > 28 else "") for i, sid in enumerate(order)}   # name from observed pattern
    t["segment_name"] = t["segment_id"].map(nm)
    out = t.reset_index()[["customer_id", "segment_id", "segment_name", "active_days", "events_total",
                           "events_per_active_day", "buys_total", "recency_days"]].round(2)
    out.to_csv(C.OUT_DIR / "customer_segments.csv", index=False)
    summ = t.groupby("segment_name").agg(customers=("events_total", "size"), avg_events=("events_total", "mean"),
                                         avg_active_days=("active_days", "mean"), avg_events_per_active_day=("events_per_active_day", "mean"),
                                         avg_buys=("buys_total", "mean"), avg_recency_days=("recency_days", "mean")).round(2)
    summ["share_pct"] = (summ["customers"] / summ["customers"].sum() * 100).round(1)
    summ = summ.loc[[nm[sid] for sid in order]]; summ.to_csv(C.TABLES / "segment_summary.csv")
    print(f"K-Means: k={k} (silhouette {sil:.2f}) | {len(out):,} customers\n", summ.to_string())


if __name__ == "__main__":
    main()
