"""
STEP 2 - Feature engineering, drift detection, classification and forecasting.

 * Daily  : EWMA + rolling Z-score  -> anomaly / drift alerts per product
 * Weekly : features built ONLY from the past, label built from the NEXT week
            (no data leakage), chronological train/test split
            models = Logistic Regression, Random Forest, (XGBoost if installed)
 * Forecast: damped-trend exponential smoothing with 80 % interval (next 4 weeks)
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C

CLASSES = ["Decreasing", "Stable", "Increasing"]
FEATURES = ["log_interest", "growth_1w", "growth_3w", "ewma_gap", "zscore_4w", "slope_4w",
            "cart_growth_1w", "buy_growth_1w", "cart_to_buy", "remove_ratio",
            "category_growth_1w", "price"]


# ----------------------------------------------------------------------------- load
def load():
    dp = pd.read_csv(C.OUT_DIR / "daily_product.csv", parse_dates=["date"])
    props = pd.read_csv(C.OUT_DIR / "products.csv").rename(columns={C.COL_SKU: "sku", C.COL_CATEGORY: "category", C.COL_PRICE: "price"}) \
        if (C.OUT_DIR / "products.csv").exists() else pd.DataFrame(columns=["sku", "category", "price"])
    props = props.drop_duplicates("sku")
    w = C.INTEREST_WEIGHTS
    dp["interest"] = w["views"] * dp["views"] + w["carts"] * dp["carts"] + w["buys"] * dp["buys"]
    tot = dp.groupby("sku")["interest"].sum()
    keep = tot[tot >= C.MIN_TOTAL_INTEREST].sort_values(ascending=False).head(C.MAX_PRODUCTS).index
    dp = dp[dp["sku"].isin(keep)]
    return dp, props


def dense(dp, col, skus, days):
    p = dp.pivot_table(index="sku", columns="date", values=col, aggfunc="sum")
    return p.reindex(index=skus, columns=days).fillna(0.0)


# ----------------------------------------------------------------------------- daily drift
def daily_drift(dp, skus, days):
    I = dense(dp, "interest", skus, days).T                     # days x skus
    ew = I.ewm(span=C.EWMA_SPAN, adjust=False).mean()
    prev = I.shift(1).rolling(28, min_periods=7)
    mu, sd = prev.mean(), prev.std()
    z = (I - mu) / (sd + np.maximum(1.0, 0.1 * mu))
    z = z.fillna(0.0)
    return I, ew, z, mu


# ----------------------------------------------------------------------------- weekly panel
def weekly(mats, days):
    D = len(days)
    W = D // 7
    cut = D - W * 7
    out = {}
    for k, m in mats.items():
        a = m.values[:, cut:]
        out[k] = a.reshape(a.shape[0], W, 7).sum(axis=2)
    week_start = [days[cut + 7 * i] for i in range(W)]
    return out, week_start


def build_features(Wk, I, cat_idx, price, W):
    S = I.shape[0]
    n_cat = cat_idx.max() + 1
    catI = np.zeros((n_cat, W))
    np.add.at(catI, cat_idx, I)
    rows = []
    for t in range(3, W):
        i0, i1, i2, i3 = I[:, t], I[:, t - 1], I[:, t - 2], I[:, t - 3]
        past3 = np.stack([i1, i2, i3])
        m3 = past3.mean(0)
        ew = 0.5 * i0 + 0.25 * i1 + 0.125 * i2 + 0.125 * i3
        win = I[:, t - 3:t + 1]
        slope = np.polyfit(np.arange(4), win.T, 1)[0] / (win.mean(1) + 5)
        c0, c1 = Wk["carts"][:, t], Wk["carts"][:, t - 1]
        b0, b1 = Wk["buys"][:, t], Wk["buys"][:, t - 1]
        cg = (catI[:, t] - catI[:, t - 1]) / (catI[:, t - 1] + 5)
        f = pd.DataFrame({
            "log_interest": np.log1p(i0),
            "growth_1w": (i0 - i1) / (i1 + 5),
            "growth_3w": (i0 - m3) / (m3 + 5),
            "ewma_gap": (i0 - ew) / (ew + 5),
            "zscore_4w": (i0 - m3) / (past3.std(0) + np.maximum(1.0, 0.1 * m3)),
            "slope_4w": slope,
            "cart_growth_1w": (c0 - c1) / (c1 + 5),
            "buy_growth_1w": (b0 - b1) / (b1 + 5),
            "cart_to_buy": b0 / (c0 + 1),
            "remove_ratio": Wk["removes"][:, t] / (c0 + 1),
            "category_growth_1w": cg[cat_idx],
            "price": price,
        })
        f["sku_idx"], f["t"] = np.arange(S), t
        base = win.mean(1)
        f["base"] = base
        if t + 1 < W:
            ratio = (I[:, t + 1] - base) / (base + 5)
            f["label"] = np.where(ratio < -C.CHANGE_THRESHOLD, 0, np.where(ratio > C.CHANGE_THRESHOLD, 2, 1))
        else:
            f["label"] = -1
        rows.append(f)
    return pd.concat(rows, ignore_index=True)


# ----------------------------------------------------------------------------- forecast
def holt_damped(I, H, alpha=0.5, beta=0.2, phi=0.9):
    S, W = I.shape
    lvl = I[:, :2].mean(1)
    tr = (I[:, 1] - I[:, 0]) * 0.5
    res = []
    for t in range(W):
        pred = lvl + phi * tr
        res.append(I[:, t] - pred)
        new = alpha * I[:, t] + (1 - alpha) * pred
        tr = beta * (new - lvl) + (1 - beta) * phi * tr
        lvl = new
    sigma = np.std(np.stack(res[2:]), axis=0)
    mean = np.zeros((S, H)); cum = np.zeros(S)
    for h in range(1, H + 1):
        cum = cum + phi ** h
        mean[:, h - 1] = np.maximum(0, lvl + cum * tr)
    hh = np.sqrt(np.arange(1, H + 1))[None, :]
    lo = np.maximum(0, mean - 1.28 * sigma[:, None] * hh)
    hi = mean + 1.28 * sigma[:, None] * hh
    return mean, lo, hi


# ----------------------------------------------------------------------------- models
def make_models():
    m = {
        "Logistic Regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")),
        "Random Forest": RandomForestClassifier(n_estimators=250, min_samples_leaf=5, class_weight="balanced_subsample",
                                                n_jobs=-1, random_state=C.RANDOM_STATE),
    }
    try:
        from xgboost import XGBClassifier
        m["XGBoost"] = XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.06, subsample=0.85,
                                     colsample_bytree=0.85, eval_metric="mlogloss", random_state=C.RANDOM_STATE, n_jobs=-1)
    except Exception:
        pass
    return m


def sample_weight(y):
    cnt = np.bincount(y, minlength=3).astype(float)
    return (len(y) / (3 * np.maximum(cnt, 1)))[y]


def main():
    dp, props = load()
    days = pd.date_range(dp["date"].min(), dp["date"].max())
    skus = np.array(sorted(dp["sku"].unique()))
    print(f"{len(skus)} products | {len(days)} days | {days[0].date()} -> {days[-1].date()}")

    props = props.set_index("sku").reindex(skus)
    cat_codes = pd.Categorical(props["category"].fillna(-1)).codes
    price = props["price"].fillna(props["price"].median() if props["price"].notna().any() else 0).values

    # ---------- daily
    mats = {k: dense(dp, k, skus, days) for k in ["views", "carts", "removes", "buys", "interest"]}
    Id, ew, z, mu = daily_drift(dp, skus, days)

    # ---------- weekly
    Wk, week_start = weekly(mats, days)
    W = Wk["interest"].shape[1]
    I = Wk["interest"]
    print("weeks:", W)
    if W < 8:
        raise SystemExit("Need at least 8 full weeks of data for training.")

    F = build_features(Wk, I, cat_codes, price, W)
    lab = F[(F["label"] >= 0) & (F["base"] >= C.MIN_BASE_INTEREST)]
    t_last = W - 2
    test_t = [t_last - 1, t_last]
    tr = lab[lab["t"] <= t_last - 3 + 0]          # gap of one week => no overlap of label windows
    te = lab[lab["t"].isin(test_t)]
    Xtr, ytr = tr[FEATURES].values, tr["label"].values.astype(int)
    Xte, yte = te[FEATURES].values, te["label"].values.astype(int)
    print(f"train rows {len(tr):,} | test rows {len(te):,} | class balance train {np.bincount(ytr, minlength=3)}")

    # naive baseline: "last week's direction continues"
    nb = np.where(te["growth_1w"] < -C.CHANGE_THRESHOLD, 0, np.where(te["growth_1w"] > C.CHANGE_THRESHOLD, 2, 1))
    report = {"models": {}, "baseline": {"name": "Naive (last week's direction)",
              "accuracy": float(accuracy_score(yte, nb)), "macro_f1": float(f1_score(yte, nb, average="macro"))}}

    models = make_models()
    fitted = {}
    for name, mdl in models.items():
        kw = {}
        if name == "XGBoost":
            kw["sample_weight"] = sample_weight(ytr)
        mdl.fit(Xtr, ytr, **kw)
        p = mdl.predict(Xte)
        report["models"][name] = {
            "accuracy": float(accuracy_score(yte, p)),
            "macro_f1": float(f1_score(yte, p, average="macro")),
            "f1_per_class": [float(x) for x in f1_score(yte, p, average=None, labels=[0, 1, 2], zero_division=0)],
            "confusion": confusion_matrix(yte, p, labels=[0, 1, 2]).tolist(),
        }
        fitted[name] = mdl
        print(f"{name:20s} acc={report['models'][name]['accuracy']:.3f}  macroF1={report['models'][name]['macro_f1']:.3f}")
    best = max(report["models"], key=lambda k: report["models"][k]["macro_f1"])
    print("best:", best, "| baseline acc", round(report["baseline"]["accuracy"], 3))

    # feature importance (Random Forest, always available)
    rf = fitted["Random Forest"]
    report["feature_importance"] = sorted(
        [{"feature": f, "importance": float(v)} for f, v in zip(FEATURES, rf.feature_importances_)],
        key=lambda d: -d["importance"])

    # refit best model on ALL labelled rows, predict the latest week -> next 7 days
    full = lab
    final = make_models()[best]
    kw = {"sample_weight": sample_weight(full["label"].values.astype(int))} if best == "XGBoost" else {}
    final.fit(full[FEATURES].values, full["label"].values.astype(int), **kw)
    cur = F[F["t"] == W - 1].sort_values("sku_idx")
    proba = final.predict_proba(cur[FEATURES].values)
    pred = proba.argmax(1)

    report["best_model"] = best
    report["dataset"] = {
        "products_modelled": int(len(skus)), "days": int(len(days)), "weeks": int(W),
        "date_from": str(days[0].date()), "date_to": str(days[-1].date()),
        "train_rows": int(len(tr)), "test_rows": int(len(te)),
        "train_weeks": f"{week_start[3].date()} -> {week_start[t_last - 3].date()}",
        "test_weeks": f"{week_start[test_t[0]].date()} -> {week_start[test_t[1]].date()}",
        "label_distribution_train": {CLASSES[i]: int(c) for i, c in enumerate(np.bincount(ytr, minlength=3))},
        "change_threshold": C.CHANGE_THRESHOLD, "weights": C.INTEREST_WEIGHTS,
        "features": FEATURES,
    }
    meta = json.loads((C.OUT_DIR / "meta.json").read_text()) if (C.OUT_DIR / "meta.json").exists() else {}
    report["dataset"]["has_product_views"] = bool(meta.get("has_product_views", False))

    # ---------- forecast
    fm, flo, fhi = holt_damped(I, C.FORECAST_WEEKS)
    fc_rows = []
    for h in range(C.FORECAST_WEEKS):
        ws = week_start[-1] + pd.Timedelta(days=7 * (h + 1))
        fc_rows.append(pd.DataFrame({"sku": skus, "h": h + 1, "week_start": ws.date(),
                                     "mean": fm[:, h].round(1), "lo": flo[:, h].round(1), "hi": fhi[:, h].round(1)}))
    pd.concat(fc_rows).to_csv(C.OUT_DIR / "forecast.csv", index=False)

    # ---------- weekly export
    wk_rows = []
    for i, ws in enumerate(week_start):
        wk_rows.append(pd.DataFrame({"sku": skus, "week_start": ws.date(), **{k: Wk[k][:, i] for k in ["views", "carts", "removes", "buys", "interest"]}}))
    pd.concat(wk_rows).to_csv(C.OUT_DIR / "weekly_top.csv", index=False)

    # ---------- daily export
    cut = len(days) - W * 7
    dd = pd.DataFrame({"date": np.tile(days, len(skus)), "sku": np.repeat(skus, len(days))})
    for k in ["views", "carts", "removes", "buys"]:
        dd[k] = mats[k].values.reshape(-1).astype(int)
    dd["interest"] = mats["interest"].values.reshape(-1).round(1)
    dd["ewma"] = ew.T.values.reshape(-1).round(2)
    dd["z"] = z.T.values.reshape(-1).round(2)
    dd["baseline"] = mu.T.fillna(0).values.reshape(-1).round(2)
    dd.to_csv(C.OUT_DIR / "daily_top.csv", index=False)

    # ---------- alerts (last 21 days)
    recent = dd[(dd["date"] > days[-1] - pd.Timedelta(days=21)) & ((dd["z"] >= C.Z_ALERT) | (dd["z"] <= -C.Z_DROP)) & (dd["baseline"] >= 3)].copy()
    recent["direction"] = np.where(recent["z"] > 0, "Spike", "Drop")
    recent.sort_values(["date", "z"], ascending=[False, False]).to_csv(C.OUT_DIR / "alerts.csv", index=False)

    # ---------- product stats
    def win(a, lo, hi):  # sum over day columns [lo,hi)
        return a[:, lo:hi].sum(1)
    Dn = len(days)
    ival = mats["interest"].values
    i7, p7 = win(ival, Dn - 7, Dn), win(ival, Dn - 14, Dn - 7)
    i28, p28 = win(ival, Dn - 28, Dn), win(ival, Dn - 56, Dn - 28)
    ch = lambda a, b: np.where(b > 0, (a - b) / np.maximum(b, 1) * 100, 0.0)
    ch7, ch28 = ch(i7, p7), ch(i28, p28)
    thr = 15
    trend = np.where(i7 + p7 < 15, "Low volume", np.where(ch7 >= thr, "Rising", np.where(ch7 <= -thr, "Declining", "Stable")))
    buys28, carts28 = win(mats["buys"].values, Dn - 28, Dn), win(mats["carts"].values, Dn - 28, Dn)
    stats = pd.DataFrame({
        "sku": skus, "category": props["category"].fillna(-1).astype(int).values, "price": props["price"].values,
        "interest_7d": i7.round(1), "prev_7d": p7.round(1), "change_7d": ch7.round(1),
        "interest_28d": i28.round(1), "prev_28d": p28.round(1), "change_28d": ch28.round(1),
        "views_7d": win(mats["views"].values, Dn - 7, Dn).astype(int),
        "carts_7d": win(mats["carts"].values, Dn - 7, Dn).astype(int),
        "removes_7d": win(mats["removes"].values, Dn - 7, Dn).astype(int),
        "buys_7d": win(mats["buys"].values, Dn - 7, Dn).astype(int),
        "conversion_28d": np.where(carts28 > 0, buys28 / np.maximum(carts28, 1) * 100, 0).round(1),
        "trend": trend,
        "pred_label": [CLASSES[i] for i in pred],
        "p_down": proba[:, 0].round(3), "p_stable": proba[:, 1].round(3), "p_up": proba[:, 2].round(3),
        "confidence": proba.max(1).round(3),
        "z_latest": z.values[-1].round(2),
        "fc_next_week": fm[:, 0].round(1),
        "fc_change_pct": np.where(I[:, -1] > 0, (fm[:, 0] - I[:, -1]) / np.maximum(I[:, -1], 1) * 100, 0).round(1),
        "low_volume": (I[:, -4:].mean(1) < C.MIN_BASE_INTEREST),
    })
    stats["rank"] = stats["interest_28d"].rank(ascending=False, method="first").astype(int)
    stats.to_csv(C.OUT_DIR / "product_stats.csv", index=False)
    (C.OUT_DIR / "model_report.json").write_text(json.dumps(report, indent=2))
    print("saved ->", C.OUT_DIR)


if __name__ == "__main__":
    main()
