"""
DRIFTEX Product Interest Intelligence - web server (python standard library only + pandas).
Run:  python app/server.py      then open http://localhost:8000
"""
import json, sys, math
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
import config as C

P = C.OUT_DIR
STATIC = Path(__file__).resolve().parent / "static"


def load():
    d = {}
    try:
        d["comp"] = pd.read_csv(P / "daily_company.csv", parse_dates=["date"]).sort_values("date")
        d["stats"] = pd.read_csv(P / "product_stats.csv")
        d["daily"] = pd.read_csv(P / "daily_top.csv", parse_dates=["date"])
        d["weekly"] = pd.read_csv(P / "weekly_top.csv")
        d["fc"] = pd.read_csv(P / "forecast.csv")
        d["alerts"] = pd.read_csv(P / "alerts.csv", parse_dates=["date"])
        d["report"] = json.loads((P / "model_report.json").read_text())
    except FileNotFoundError as e:
        sys.exit(f"Missing processed file: {e.filename}\nRun the pipeline first:\n"
                 "  python pipeline/01_build_metrics.py\n  python pipeline/02_train_models.py")
    d["by_sku_daily"] = {k: g.reset_index(drop=True) for k, g in d["daily"].groupby("sku")}
    d["by_sku_week"] = {k: g.reset_index(drop=True) for k, g in d["weekly"].groupby("sku")}
    d["by_sku_fc"] = {k: g.reset_index(drop=True) for k, g in d["fc"].groupby("sku")}
    d["I"] = d["daily"].pivot(index="date", columns="sku", values="interest")
    d["B"] = d["I"].shift(1).rolling(7, min_periods=3).mean()
    d["stats_i"] = d["stats"].set_index("sku")
    return d


D = load()


def clean(o):
    if isinstance(o, dict):  return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating, float)):
        return None if (math.isnan(o) or math.isinf(o)) else float(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    if isinstance(o, (pd.Timestamp,)): return o.strftime("%Y-%m-%d")
    return o


def records(df):
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.strftime("%Y-%m-%d")
    return clean(df.to_dict("records"))


def pct(a, b):
    return 0.0 if not b else round((a - b) / b * 100, 1)


# ------------------------------------------------------------------ API
def api_meta(q):
    c = D["comp"]
    return {"date_from": c["date"].min(), "date_to": c["date"].max(), "n_products": len(D["stats"]),
            "has_product_views": D["report"]["dataset"]["has_product_views"],
            "best_model": D["report"]["best_model"],
            "categories": sorted(int(x) for x in D["stats"]["category"].unique())}


def api_summary(q):
    c = D["comp"].set_index("date")
    cols = ["visits", "searches", "carts", "removes", "buys"]
    last, prev = c.iloc[-7:], c.iloc[-14:-7]
    kpi = {k: {"value": int(last[k].sum()), "prev": int(prev[k].sum()), "change": pct(last[k].sum(), prev[k].sum())} for k in cols}
    conv = lambda x: x["buys"].sum() / max(x["carts"].sum(), 1) * 100
    kpi["conversion"] = {"value": round(conv(last), 1), "prev": round(conv(prev), 1), "change": round(conv(last) - conv(prev), 1), "unit": "pp"}
    s = D["stats"]
    active = s[~s["low_volume"]]
    counts = active["trend"].value_counts().to_dict()
    pred = active["pred_label"].value_counts().to_dict()
    n = int(q.get("n", [90])[0])
    series = c.reset_index().tail(n)
    return {"kpi": kpi, "series": records(series), "trend_counts": counts, "pred_counts": pred,
            "funnel": {k: int(last[k].sum()) for k in ["visits", "carts", "buys"]},
            "top_rising": records(active.sort_values("change_7d", ascending=False).query("trend=='Rising'").head(6)[["sku", "category", "interest_7d", "change_7d", "pred_label"]]),
            "top_declining": records(active.sort_values("change_7d").query("trend=='Declining'").head(6)[["sku", "category", "interest_7d", "change_7d", "pred_label"]])}


def api_products(q):
    s = D["stats"].copy()
    g = lambda k, d="": q.get(k, [d])[0]
    if g("q"): s = s[s["sku"].astype(str).str.contains(g("q"))]
    if g("category") not in ("", "all"): s = s[s["category"] == int(g("category"))]
    if g("trend") not in ("", "all"): s = s[s["trend"] == g("trend")]
    if g("pred") not in ("", "all"): s = s[s["pred_label"] == g("pred")]
    if g("hide_low") == "1": s = s[~s["low_volume"]]
    sort = g("sort", "interest_28d")
    if sort not in s.columns: sort = "interest_28d"
    s = s.sort_values(sort, ascending=(g("dir") == "asc"))
    total = len(s)
    page, size = int(g("page", 1)), int(g("size", 15))
    s = s.iloc[(page - 1) * size: page * size]
    return {"total": total, "page": page, "size": size, "rows": records(s)}


def insights(st, wk):
    out = []
    c7, c28 = st["change_7d"], st["change_28d"]
    if st["trend"] == "Low volume":
        out.append("Activity is too low for a reliable trend; treat the forecast with caution.")
    else:
        word = "increased" if c7 > 0 else "decreased"
        out.append(f"Interest {word} by {abs(c7):.0f}% in the last 7 days versus the previous 7 days "
                   f"({abs(c28):.0f}% {'up' if c28 > 0 else 'down'} over 28 days).")
    out.append(f"Model expects the next 7 days to be '{st['pred_label']}' (confidence {st['confidence']*100:.0f}%).")
    if st["conversion_28d"] and st["carts_7d"]:
        rr = st["removes_7d"] / max(st["carts_7d"], 1)
        if rr > 0.45: out.append(f"High cart-removal ratio ({rr*100:.0f}% of add-to-carts) suggests purchase hesitation.")
    if abs(st["z_latest"]) >= C.Z_ALERT:
        out.append(f"Today's activity is a statistical {'spike' if st['z_latest']>0 else 'drop'} (z = {st['z_latest']:+.1f}).")
    if st["pred_label"] == "Decreasing" and st["trend"] == "Declining":
        out.append("Recommended action: review pricing, stock and promotion for this product.")
    elif st["pred_label"] == "Increasing" and st["trend"] in ("Rising", "Stable"):
        out.append("Recommended action: ensure stock availability and consider featuring this product.")
    return out


def api_product(q, sku):
    sku = int(sku)
    if sku not in D["by_sku_daily"]:
        return {"error": "unknown product"}
    n = int(q.get("days", [90])[0])
    st = D["stats_i"].loc[sku].to_dict(); st["sku"] = sku
    daily = D["by_sku_daily"][sku].tail(n)
    wk, fc = D["by_sku_week"][sku], D["by_sku_fc"][sku]
    cat_peers = D["stats"][D["stats"]["category"] == st["category"]]
    return clean({"stats": st, "daily": records(daily[["date", "views", "carts", "removes", "buys", "interest", "ewma", "z", "baseline"]]),
                  "weekly": records(wk), "forecast": records(fc),
                  "insights": insights(st, wk),
                  "category_rank": {"rank": int((cat_peers["interest_28d"] > st["interest_28d"]).sum() + 1), "of": len(cat_peers)}})


def api_categories(q):
    s, dd = D["stats"], D["daily"]
    g = s.groupby("category").agg(products=("sku", "count"), interest_7d=("interest_7d", "sum"), prev_7d=("prev_7d", "sum"),
                                  interest_28d=("interest_28d", "sum"), prev_28d=("prev_28d", "sum"),
                                  rising=("trend", lambda x: (x == "Rising").sum()),
                                  declining=("trend", lambda x: (x == "Declining").sum())).reset_index()
    g["change_7d"] = [pct(a, b) for a, b in zip(g["interest_7d"], g["prev_7d"])]
    g["change_28d"] = [pct(a, b) for a, b in zip(g["interest_28d"], g["prev_28d"])]
    cat = s.set_index("sku")["category"]
    t = dd.assign(category=dd["sku"].map(cat)).groupby(["category", "date"])["interest"].sum().reset_index()
    t = t[t["date"] >= t["date"].max() - pd.Timedelta(days=55)]
    spark = {int(k): [round(v, 1) for v in grp.sort_values("date")["interest"].tolist()] for k, grp in t.groupby("category")}
    g["spark"] = g["category"].map(spark)
    return {"rows": records(g.sort_values("interest_28d", ascending=False))}


def api_alerts(q):
    a = D["alerts"].copy()
    kind = q.get("kind", ["all"])[0]
    if kind in ("Spike", "Drop"): a = a[a["direction"] == kind]
    a = a.sort_values(["date", "z"], key=lambda col: col if col.name == "date" else col.abs(), ascending=False).head(int(q.get("n", [60])[0]))
    a = a.merge(D["stats"][["sku", "category"]], on="sku", how="left")
    return {"rows": records(a[["date", "sku", "category", "direction", "interest", "baseline", "z"]]),
            "total_spikes": int((D["alerts"]["direction"] == "Spike").sum()), "total_drops": int((D["alerts"]["direction"] == "Drop").sum())}


def api_model(q):
    return D["report"]


def api_live(q):
    dates = list(D["I"].index)
    start = max(0, len(dates) - 45)
    return {"dates": [d.strftime("%Y-%m-%d") for d in dates[start:]]}


def api_live_day(q):
    d = pd.Timestamp(q["date"][0])
    c = D["comp"].set_index("date")
    if d not in c.index: return {"error": "date"}
    row = c.loc[d].to_dict()
    cur, base = D["I"].loc[d], D["B"].loc[d]
    delta = (cur - base)
    ok = base >= 6
    mv = pd.DataFrame({"sku": cur.index, "now": cur.values, "baseline": base.values, "delta": delta.values})[ok.values]
    mv["change"] = (mv["delta"] / mv["baseline"] * 100).round(0)
    cat = D["stats_i"]["category"]
    mv["category"] = mv["sku"].map(cat)
    up = mv.sort_values("delta", ascending=False).head(4)
    dn = mv.sort_values("delta").head(4)
    return {"date": d, "company": row, "up": records(up), "down": records(dn)}


ROUTES = {"/api/meta": api_meta, "/api/summary": api_summary, "/api/products": api_products, "/api/categories": api_categories,
          "/api/alerts": api_alerts, "/api/model": api_model, "/api/live": api_live, "/api/live/day": api_live_day}


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(STATIC), **k)

    def log_message(self, *a): pass

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        try:
            if u.path.startswith("/api/product/"):
                return self.send_json(api_product(q, u.path.rsplit("/", 1)[1]))
            if u.path in ROUTES:
                return self.send_json(ROUTES[u.path](q))
        except Exception as e:
            return self.send_json({"error": str(e)}, 500)
        if u.path == "/": self.path = "/index.html"
        return super().do_GET()

    def send_json(self, obj, code=200):
        b = json.dumps(clean(obj)).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"DRIFTEX dashboard running -> http://localhost:{port}   (Ctrl+C to stop)")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
