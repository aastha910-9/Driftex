"""DRIFTEX dashboard (restyled). Launch:  streamlit run src/dashboard/app.py
Light/Dark: Streamlit menu (top right) > Settings > Theme. Default is dark (see .streamlit/config.toml)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config as C
from src.drift.detect import compute_drift

st.set_page_config(page_title="DRIFTEX | Customer Retention Intelligence", page_icon="📈", layout="wide")

LIME, AMBER, ORANGE, VIOLET, SKY, GREY, RED, GREEN = "#B6E83A", "#F5C518", "#FF8A3D", "#9B6BFF", "#38BDF8", "#6B6790", "#FF5A5F", "#B6E83A"
CMAP = {"conventional": GREY, "drift_enhanced": LIME}

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Lilita+One&family=Oswald:wght@400;500;600&display=swap');
:root{--line:rgba(255,255,255,.13);--soft:rgba(255,255,255,.035)}
[data-testid="stAppViewContainer"]{background-image:radial-gradient(900px 380px at 50% 115%,rgba(120,210,40,.26),transparent),radial-gradient(700px 360px at 92% -8%,rgba(155,107,255,.15),transparent)}
.block-container{padding-top:1.2rem;max-width:1400px}
footer{visibility:hidden}
[data-testid="stAppDeployButton"],.stDeployButton{display:none}
h1,h2,h3{font-family:'Lilita One',sans-serif;font-weight:400;letter-spacing:.02em}
h2,h3{border-bottom:2px solid rgba(182,232,58,.35);padding-bottom:.3rem}
.hero{display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap;padding:18px 24px;margin-bottom:1rem;
 border:1px solid rgba(182,232,58,.35);border-top:3px solid #B6E83A;border-radius:16px;
 background:linear-gradient(135deg,rgba(182,232,58,.12),rgba(155,107,255,.08))}
.hero h1{margin:0;padding:0;font-size:2.1rem;letter-spacing:.04em}
.hero h1 span{color:#B6E83A}
.hero p{margin:.2rem 0 0;opacity:.78;font-size:.95rem}
.pill{border:1px solid rgba(182,232,58,.5);border-radius:999px;padding:6px 14px;font-size:.8rem;color:#DDF58A}
[data-testid="stMetric"]{border:1px solid var(--line);border-left:4px solid #B6E83A;border-radius:14px;padding:14px 16px;background:var(--soft)}
[data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"],[data-testid="column"]:nth-child(2) [data-testid="stMetric"]{border-left-color:#F5C518}
[data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"],[data-testid="column"]:nth-child(3) [data-testid="stMetric"]{border-left-color:#FF8A3D}
[data-testid="stColumn"]:nth-child(4) [data-testid="stMetric"],[data-testid="column"]:nth-child(4) [data-testid="stMetric"]{border-left-color:#9B6BFF}
[data-testid="stColumn"]:nth-child(5) [data-testid="stMetric"],[data-testid="column"]:nth-child(5) [data-testid="stMetric"]{border-left-color:#38BDF8}
[data-testid="stMetricLabel"] p{white-space:normal;font-family:'Oswald',sans-serif;text-transform:uppercase;letter-spacing:.09em;font-size:.78rem;opacity:.85}
[data-testid="stMetricValue"]{font-size:1.6rem}
[data-testid="stMetricValue"] > div{font-family:'Lilita One',sans-serif;overflow:visible;text-overflow:clip;white-space:normal;
 background:linear-gradient(90deg,#F5C518,#B6E83A);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
[data-testid="stPlotlyChart"]{border:1px solid var(--line);border-radius:14px;padding:6px;background:var(--soft)}
[data-testid="stDataFrame"],[data-testid="stExpander"]{border:1px solid var(--line);border-radius:14px}
[data-testid="stImage"] img{border:1px solid var(--line);border-radius:14px}
[data-testid="stAlert"]{border-radius:14px}
span[data-baseweb="tag"]{background:#B6E83A !important}
span[data-baseweb="tag"],span[data-baseweb="tag"] *{color:#0C0A1D !important}
[data-testid="stDownloadButton"] button{background:#fff;border:2px solid #0C0A1D;border-radius:10px;box-shadow:4px 4px 0 #B6E83A;transition:all .15s}
[data-testid="stDownloadButton"] button,[data-testid="stDownloadButton"] button p{color:#0C0A1D !important;font-weight:700}
[data-testid="stDownloadButton"] button:hover{transform:translate(2px,2px);box-shadow:2px 2px 0 #B6E83A;background:#fff}
/* ---------- sidebar ---------- */
[data-testid="stSidebar"]{background:radial-gradient(500px 260px at 50% 108%,rgba(120,210,40,.24),transparent),linear-gradient(180deg,#0E0B22,#0A0818);border-right:1px solid rgba(182,232,58,.22)}
.brand{display:flex;align-items:center;gap:12px;padding:6px 4px 18px;border-bottom:1px solid rgba(255,255,255,.09);margin-bottom:4px}
.brand svg{flex:none;filter:drop-shadow(3px 3px 0 rgba(255,138,61,.55))}
.brand b{display:block;color:#fff;font-family:'Lilita One',sans-serif;font-weight:400;font-size:1.45rem;letter-spacing:.05em;line-height:1.1}
.brand b em{font-style:normal;color:#B6E83A}
.brand span{display:block;color:#A29FC8;font-size:.72rem}
.navgroup{color:#8C88B8;font-family:'Oswald',sans-serif;font-size:.72rem;letter-spacing:.18em;font-weight:600;margin:20px 4px 6px}
[data-testid="stSidebar"] .stButton button{border:2px solid transparent;background:transparent;color:#E9E6FF;box-shadow:none;padding:.6rem .85rem;border-radius:12px;
 font-family:'Oswald',sans-serif;font-weight:500;font-size:1rem;letter-spacing:.03em;transition:all .15s ease}
[data-testid="stSidebar"] .stButton button > div{justify-content:flex-start;width:100%;gap:.5rem}
[data-testid="stSidebar"] .stButton button p{text-align:left;color:inherit}
[data-testid="stSidebar"] .stButton button:hover{background:rgba(182,232,58,.09);color:#B6E83A;transform:translateX(4px)}
[data-testid="stSidebar"] .stButton button[kind="primary"],[data-testid="stSidebar"] .stButton button[data-testid="stBaseButton-primary"]{
 background:#fff;color:#0C0A1D;border-color:#0C0A1D;font-weight:600;box-shadow:4px 4px 0 #B6E83A;transform:none}
[data-testid="stSidebar"] .stButton button[kind="primary"] p,[data-testid="stSidebar"] .stButton button[data-testid="stBaseButton-primary"] p{color:#0C0A1D}
.snap{border:1px solid rgba(182,232,58,.28);border-radius:16px;padding:12px 14px;background:rgba(255,255,255,.04);margin-top:20px}
.snap h6{margin:0 0 6px;color:#8C88B8;font-family:'Oswald',sans-serif;font-size:.72rem;letter-spacing:.18em;font-weight:600}
.snap .row{display:flex;justify-content:space-between;align-items:baseline;padding:6px 0;border-bottom:1px dashed rgba(255,255,255,.1);color:#B9B6DA;font-size:.78rem}
.snap .row:last-child{border-bottom:0}
.snap .row b{font-family:'Lilita One',sans-serif;font-weight:400;font-size:1.15rem;background:linear-gradient(90deg,#F5C518,#B6E83A);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
[data-testid="stSidebar"] [data-testid="stExpander"]{border:1px solid rgba(182,232,58,.22);background:rgba(255,255,255,.03);border-radius:14px;margin-top:10px}
[data-testid="stSidebar"] [data-testid="stExpander"] *{color:#D5D2F0}
.sidefoot{margin-top:22px;padding-top:12px;border-top:1px solid rgba(255,255,255,.09);color:#A29FC8;font-size:.75rem;line-height:1.5}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#B6E83A;margin-right:6px;box-shadow:0 0 8px #B6E83A}
</style>""", unsafe_allow_html=True)


@st.cache_data
def csv(name, **kw):
    p = C.OUT_DIR / name
    return pd.read_csv(p, **kw) if p.exists() else None


@st.cache_data
def table(name):
    p = C.TABLES / name
    return pd.read_csv(p) if p.exists() else None


@st.cache_data(show_spinner="Loading test predictions (10% sample)...")
def pred_sample(frac=0.1):
    p = C.OUT_DIR / "predictions.csv"
    if not p.exists():
        return None
    cols = ["model_name", "feature_set", "inactive_30d", "predicted_probability"]
    return pd.concat([c.sample(frac=frac, random_state=0) for c in pd.read_csv(p, usecols=cols, chunksize=1_000_000)], ignore_index=True)


def jload(name):
    p = C.TABLES / name
    return json.loads(p.read_text()) if p.exists() else None


def need(df, msg):
    if df is None:
        st.warning(f"{msg} Run `python run_all.py` first.")
        st.stop()
    return df


def show(fig, unified=True):
    """Streamlit's own theme restyles the chart for light/dark; we only set layout and spacing."""
    fig.update_layout(margin=dict(l=10, r=10, t=55, b=10), legend=dict(orientation="h", y=1.1, x=0))
    if unified:
        fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)


GROUPS = [("MONITOR", [("Overview", ":material/space_dashboard:"), ("Behaviour & Drift", ":material/show_chart:")]),
          ("INTELLIGENCE", [("Prediction & Explanation", ":material/insights:"), ("Segments & Value Priority", ":material/groups:")])]
if "section" not in st.session_state:
    st.session_state.section = "Overview"


def sbtn(label, icon, key, primary=False):
    kw = dict(key=key, use_container_width=True, type="primary" if primary else "secondary")
    try:
        return st.button(label, icon=icon, **kw)
    except TypeError:  # older Streamlit without button icons
        return st.button(label, **kw)


_d0, _e0 = jload("data_quality.json"), jload("experiment_summary.json")
with st.sidebar:
    st.markdown('<div class="brand"><svg width="44" height="44" viewBox="0 0 44 44"><rect width="44" height="44" rx="13" fill="#B6E83A"/><path d="M7 15 C14 15 15 12 20 17 S28 29 37 30" fill="none" stroke="#0C0A1D" stroke-width="3.4" stroke-linecap="round"/><circle cx="37" cy="30" r="4" fill="#FF8A3D" stroke="#0C0A1D" stroke-width="2"/></svg><div><b>DRIFT<em>EX</em></b><span>Behaviour drift intelligence</span></div></div>', unsafe_allow_html=True)
    for _g, _items in GROUPS:
        st.markdown(f'<div class="navgroup">{_g}</div>', unsafe_allow_html=True)
        for _it, _ic in _items:
            if sbtn(_it, _ic, f"nav_{_it}", st.session_state.section == _it):
                st.session_state.section = _it
                st.rerun()
    _lt = (_e0 or {}).get("warning_lead_time")
    if _lt:
        st.markdown(f'''<div class="snap"><h6>LIVE SNAPSHOT</h6>
<div class="row"><span>Customers warned</span><b class="c1">{_lt["customers_warned"]:,}</b></div>
<div class="row"><span>Warning coverage</span><b class="c2">{_lt["share_warned"]:.3%}</b></div>
<div class="row"><span>Median lead time</span><b class="c3">{_lt["median_lead_days"]:.0f} days</b></div></div>''', unsafe_allow_html=True)
    st.markdown('<div class="navgroup">QUICK ACTIONS</div>', unsafe_allow_html=True)
    if sbtn("View Act-now customers", ":material/priority_high:", "qa_act"):
        st.session_state.section = "Segments & Value Priority"
        st.rerun()
    if sbtn("Refresh data", ":material/refresh:", "qa_refresh"):
        st.cache_data.clear()
        st.rerun()
    with st.expander("About & definitions"):
        st.markdown("**Drift warning:** EWMA of the customer's Z-score beyond ±0.5 for 5+ days.  \n"
                    "**Target:** no activity in the next 30 days.  \n"
                    "**Value:** relative price-bucket index, not currency or CLV.  \n"
                    "**SHAP:** explains the model, not causes.")
    st.markdown(f'''<div class="sidefoot"><div><span class="dot"></span>Data up to {_d0["date_to"] if _d0 else "n/a"}</div>
<div>Dataset: Synerise e-commerce events</div><div>Theme: top-right menu (⋮) &gt; Settings</div></div>''', unsafe_allow_html=True)
section = st.session_state.section

_dq = jload("data_quality.json")
_pill = f"Synerise e-commerce · {_dq['sample_pct']}% customer sample · {_dq['date_from']} → {_dq['date_to']}" if _dq else "Synerise e-commerce"
st.markdown(f"""<div class="hero"><div><h1>DRIFT<span>EX</span></h1><p>Customer retention intelligence: personal behaviour drift + 30-day inactivity forecasting</p></div>
<div class="pill">{_pill}</div></div>""", unsafe_allow_html=True)

# ------------------------------------------------------------------ 1. OVERVIEW
if section == "Overview":
    st.header("Overview")
    dq, ex, met = jload("data_quality.json"), jload("experiment_summary.json"), table("model_metrics.csv")
    need(dq, "Data summary not found.")
    lab = csv("inactivity_labels.csv")
    c = st.columns(5)
    c[0].metric("Customers (sample)", f"{dq['customers']:,}")
    c[1].metric("Customer-days", f"{dq['customer_days']:,}")
    c[2].metric("Date coverage", f"{dq['date_from']} → {dq['date_to']}")
    c[3].metric("Customer sample", f"{dq['sample_pct']}% of all customers")
    c[4].metric("Labelled observations", f"{len(lab):,}" if lab is not None else "–")
    if ex and ex.get("warning_lead_time"):
        lt = ex["warning_lead_time"]
        k = st.columns(3)
        k[0].metric("Customers warned by drift", f"{lt['customers_warned']:,}")
        k[1].metric("Share of inactivity episodes warned", f"{lt['share_warned']:.3%}")
        k[2].metric("Median lead over '30 days silent' rule", f"{lt['median_lead_days']:.0f} days")
    st.subheader("Workflow")
    st.markdown("**1** Customer-day aggregation → **2** Personal baseline, Z-score, EWMA, persistence warning → "
                "**3** 30-day inactivity labels and past-only features → **4** Logistic Regression / Random Forest / XGBoost, "
                "conventional vs drift-enhanced → **5** SHAP, K-Means segments, value proxy, risk priority.")
    if met is not None and ex is not None:
        st.subheader("Conventional vs drift-enhanced (same chronological test observations)")
        st.caption(f"Positive class: {ex['positive_class']} · threshold {ex['threshold']} · train ≤ {ex['train_end']} · test ≥ {ex['test_start']} · "
                   f"{ex['n_test']:,} test observations")
        m = st.selectbox("Metric", ["PR_AUC", "ROC_AUC", "F1", "Precision", "Recall"], key="ov_metric")
        left, right = st.columns([3, 2])
        with left:
            show(px.bar(met, x="model_name", y=m, color="feature_set", barmode="group", text_auto=".4f", color_discrete_map=CMAP,
                        labels={"model_name": "", "feature_set": ""}, title=f"{m} by model"), unified=False)
        pv = met.pivot(index="model_name", columns="feature_set", values=m).round(4)
        if {"conventional", "drift_enhanced"} <= set(pv.columns):
            pv["difference (drift − conventional)"] = (pv["drift_enhanced"] - pv["conventional"]).round(4)
        right.dataframe(pv, use_container_width=True)
        st.info("The comparison is the experiment: neutral or negative differences are reported as measured.")
    with st.expander("Data quality checks"):
        st.json(dq)

# ------------------------------------------------------------------ 2. BEHAVIOUR & DRIFT
elif section == "Behaviour & Drift":
    st.header("Behaviour & Drift")
    drift = need(csv("drift_features.csv", parse_dates=["date"]), "Drift features not found.")
    st.caption(f"Personal baseline = mean/SD of the customer's own previous {C.BASELINE_DAYS} days (past only). "
               f"Warning = EWMA(z, span {C.CUSTOMER_EWMA_SPAN}) beyond ±{C.DRIFT_EWMA_THRESH} for ≥ {C.PERSIST_DAYS} consecutive days.")
    share = drift.groupby("date").agg(decline=("drift_direction", lambda x: (x < 0).mean()), increase=("drift_direction", lambda x: (x > 0).mean())).reset_index()
    dirs = st.multiselect("Show warnings", ["decline", "increase"], default=["decline", "increase"])
    if dirs:
        fig = px.line(share, x="date", y=dirs, title="Share of customers with a sustained drift warning",
                      labels={"value": "share of customers", "variable": ""}, color_discrete_map={"decline": RED, "increase": GREEN})
        fig.update_yaxes(tickformat=".2%")
        fig.update_xaxes(rangeslider_visible=True)
        show(fig)

    latest = drift[drift["date"] == drift["date"].max()]
    flagged = latest[latest["drift_direction"] < 0].sort_values("drift_ewma")["customer_id"].tolist()
    st.subheader("Customer drift history")
    pick = st.selectbox("Customer (currently flagged for decline listed first)", flagged + [c for c in latest["customer_id"].tolist() if c not in set(flagged)][:200])
    act = csv("customer_daily_activity.csv", parse_dates=["date"], usecols=["customer_id", "date", "events"])
    a = act[act["customer_id"] == pick]
    days = pd.date_range(act["date"].min(), act["date"].max())
    x = a.set_index("date")["events"].reindex(days, fill_value=0).values.astype(np.float32)[None, :]
    first = np.array([int(np.argmax(x[0] > 0))])
    r = compute_drift(x, first, C.BASELINE_DAYS, C.MIN_HISTORY_DAYS, C.CUSTOMER_EWMA_SPAN, C.DRIFT_EWMA_THRESH, C.PERSIST_DAYS, C.SD_FLOOR)
    ew = r["ewma"][0]
    ew = ew[~np.isnan(ew)]
    k = st.columns(3)
    k[0].metric("Total events", f"{int(x[0].sum()):,}")
    k[1].metric("Days in decline warning", f"{int((r['direction'][0] < 0).sum())}")
    k[2].metric("Latest EWMA", f"{ew[-1]:.2f}" if len(ew) else "n/a")
    f1 = go.Figure()
    f1.add_bar(x=days, y=x[0], name="Daily events", marker_color="#8B86B8")
    f1.add_scatter(x=days, y=r["mu"][0], name="Personal baseline (past 28d mean)", line=dict(color=AMBER, width=2))
    wd = np.where(r["direction"][0] < 0)[0]
    f1.add_scatter(x=days[wd], y=r["mu"][0][wd], mode="markers", name="Decline warning", marker=dict(color=RED, size=8))
    f1.update_layout(title=f"Customer {pick}: activity vs personal baseline", height=380)
    show(f1)
    f2 = go.Figure()
    f2.add_scatter(x=days, y=r["z"][0], name="Z-score", line=dict(color=GREY))
    f2.add_scatter(x=days, y=r["ewma"][0], name="EWMA of Z", line=dict(color=LIME, width=3))
    f2.add_hline(y=-C.DRIFT_EWMA_THRESH, line_dash="dash", line_color=RED)
    f2.add_hline(y=C.DRIFT_EWMA_THRESH, line_dash="dash", line_color=GREEN)
    f2.update_layout(title="Z-score, EWMA and thresholds", height=340)
    show(f2)
    st.caption("Days before enough personal history exist are not scored (insufficient-history policy).")

# ------------------------------------------------------------------ 3. PREDICTION & EXPLANATION
elif section == "Prediction & Explanation":
    st.header("Prediction & Explanation")
    met = need(table("model_metrics.csv"), "Model metrics not found.")
    ex = jload("experiment_summary.json")
    st.subheader("Conventional vs drift-enhanced models")
    st.caption(f"Target: inactive_30d = no activity in the next 30 days (positive class). Threshold {ex['threshold']}. "
               "Both feature sets are scored on identical chronological test observations.")
    cols = ["model_name", "feature_set", "Precision", "Recall", "F1", "PR_AUC", "ROC_AUC", "positive_rate", "n"]
    st.dataframe(met[cols].round(4), use_container_width=True, hide_index=True)
    m = st.selectbox("Metric", ["PR_AUC", "ROC_AUC", "F1", "Precision", "Recall"])
    show(px.bar(met, x="model_name", y=m, color="feature_set", barmode="group", text_auto=".4f", color_discrete_map=CMAP,
                labels={"model_name": "", "feature_set": ""}), unified=False)

    ps = pred_sample()
    if ps is not None:
        st.subheader("Threshold explorer")
        st.caption("Move the threshold to see the precision / recall trade-off (computed on a 10% random sample of the test predictions).")
        t = st.slider("Decision threshold", 0.10, 0.90, float(ex["threshold"]), 0.05)
        rows = []
        for (mn, fs), g in ps.groupby(["model_name", "feature_set"]):
            y = g["inactive_30d"].values == 1
            pr = g["predicted_probability"].values >= t
            tp, fp, fn = int((y & pr).sum()), int((~y & pr).sum()), int((y & ~pr).sum())
            pre = tp / (tp + fp) if tp + fp else 0.0
            rec = tp / (tp + fn) if tp + fn else 0.0
            rows.append(dict(model_name=mn, feature_set=fs, Precision=pre, Recall=rec, F1=2 * pre * rec / (pre + rec) if pre + rec else 0.0))
        long = pd.DataFrame(rows).melt(id_vars=["model_name", "feature_set"], var_name="metric", value_name="value")
        fg = px.bar(long, x="metric", y="value", color="feature_set", facet_col="model_name", barmode="group", text_auto=".2f", color_discrete_map=CMAP,
                    labels={"metric": "", "value": "", "feature_set": ""})
        fg.for_each_annotation(lambda an: an.update(text=an.text.split("=")[-1]))
        show(fg, unified=False)

    lt = ex["warning_lead_time"]
    st.subheader("Warning lead time")
    k = st.columns(3)
    k[0].metric("Customers with inactivity episode", f"{lt['customers_with_inactivity_episode']:,}")
    k[1].metric("Warned by drift", f"{lt['customers_warned']:,} ({lt['share_warned']:.3%})")
    k[2].metric("Median lead over '30 days silent' rule", f"{lt['median_lead_days']:.0f} days")
    st.caption("Lead time = (last activity + 30 days) − first sustained-decline warning. Resolution equals the observation grid.")
    st.subheader("Predicted inactivity risk (newest observation date)")
    sc = csv("scoring_predictions.csv")
    if sc is not None:
        show(px.histogram(sc, x="predicted_probability", nbins=30, color_discrete_sequence=[LIME],
                          title=f"Distribution of predicted probabilities ({ex['best_drift_enhanced_model']})"), unified=False)
        st.caption("Probabilities are model estimates; do not read an individual score as certainty.")
    st.subheader("SHAP explanation")
    g, l = C.FIGS / "shap_global.png", C.FIGS / "shap_local.png"
    if g.exists() and l.exists():
        c1, c2 = st.columns(2)
        c1.image(str(g), caption="Global: which features drive the model output")
        c2.image(str(l), caption="One local example")
        st.caption("SHAP describes how the model uses features; it does not show causes of inactivity.")
    else:
        st.info("SHAP figures not found. Install shap and run `python -m src.insights.explain`.")

# ------------------------------------------------------------------ 4. SEGMENTS & VALUE PRIORITY
else:
    st.header("Segments & Value Priority")
    summ = need(table("segment_summary.csv"), "Segment summary not found.")
    st.subheader("K-Means engagement segments")
    c1, c2 = st.columns([1, 1])
    with c1:
        pie = px.pie(summ, names="segment_name", values="customers", hole=.5, color_discrete_sequence=[LIME, AMBER, ORANGE, VIOLET, SKY])
        pie.update_traces(textinfo="percent+label")
        show(pie, unified=False)
    c2.dataframe(summ, use_container_width=True, hide_index=True)
    val = csv("customer_value.csv")
    if val is None:
        st.warning("No reliable value data: value proxy not created. Ranking uses risk only.")
    else:
        st.subheader("Historical value proxy")
        st.caption("Sum of purchased products' price bucket — a relative index, not currency and not predicted lifetime value.")
        show(px.histogram(val[val.historical_value_proxy > 0], x="historical_value_proxy", nbins=40, log_y=True, color_discrete_sequence=[VIOLET]), unified=False)
    st.subheader("Risk priority list")
    rp = csv("risk_priority.csv")
    if rp is not None:
        st.caption("Rule: priority_score = predicted inactivity probability × value percentile (newest observation date).")
        f1c, f2c, f3c = st.columns([2, 1, 1])
        tier = f1c.multiselect("Action tier", ["Act now", "Monitor closely", "Routine"], default=["Act now"])
        q = f2c.text_input("Find customer ID")
        n = f3c.slider("Rows", 10, 200, 25)
        view = rp[rp["action_tier"].isin(tier)]
        if q:
            view = view[view["customer_id"].astype(str).str.contains(q.strip())]
        st.dataframe(view.head(n), use_container_width=True, hide_index=True)
        st.download_button("Download full priority list (CSV)", rp.to_csv(index=False), "risk_priority.csv")