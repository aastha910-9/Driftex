"""DRIFTEX dashboard - four sections (Streamlit).  Launch:  streamlit run src/dashboard/app.py"""
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

st.set_page_config(page_title="DRIFTEX", page_icon="📈", layout="wide")
st.markdown("<style>.block-container{padding-top:1.5rem}</style>", unsafe_allow_html=True)


@st.cache_data
def csv(name, **kw):
    p = C.OUT_DIR / name
    return pd.read_csv(p, **kw) if p.exists() else None


@st.cache_data
def table(name):
    p = C.TABLES / name
    return pd.read_csv(p) if p.exists() else None


def jload(name):
    p = C.TABLES / name
    return json.loads(p.read_text()) if p.exists() else None


def need(df, msg):
    if df is None:
        st.warning(f"{msg} Run `python run_all.py` first.")
        st.stop()
    return df


st.sidebar.title("DRIFTEX")
st.sidebar.caption("Personalised behaviour change detection and inactivity forecasting")
section = st.sidebar.radio("Section", ["Overview", "Behaviour & Drift", "Prediction & Explanation", "Segments & Value Priority"])
st.sidebar.divider()
st.sidebar.caption("Dataset: Synerise e-commerce events. Results are descriptive of the data used; "
                   "SHAP explains the model, not causes. Value is a historical proxy, not predicted CLV.")

# ------------------------------------------------------------------ 1. OVERVIEW
if section == "Overview":
    st.title("Overview")
    dq, ex, met = jload("data_quality.json"), jload("experiment_summary.json"), table("model_metrics.csv")
    need(dq, "Data summary not found.")
    lab = csv("inactivity_labels.csv")
    c = st.columns(5)
    c[4].metric("Labelled observations", f"{len(lab):,}" if lab is not None else "–")
    c[0].metric("Customers (sample)", f"{dq['customers']:,}")
    c[1].metric("Customer-days", f"{dq['customer_days']:,}")
    c[2].metric("Date coverage", f"{dq['date_from']} → {dq['date_to']}")
    c[3].metric("Customer sample", f"{dq['sample_pct']}% of all customers")
    st.subheader("Workflow")
    st.markdown("**1** Customer-day aggregation → **2** Personal baseline, Z-score, EWMA, persistence warning → "
                "**3** 30-day inactivity labels and past-only features → **4** Logistic Regression / Random Forest / XGBoost, "
                "conventional vs drift-enhanced → **5** SHAP, K-Means segments, value proxy, risk priority.")
    if met is not None and ex is not None:
        st.subheader("Headline evaluation (same chronological test observations)")
        st.caption(f"Positive class: {ex['positive_class']} · threshold {ex['threshold']} · train ≤ {ex['train_end']} · test ≥ {ex['test_start']} · "
                   f"{ex['n_test']:,} test observations")
        pv = met.pivot(index="model_name", columns="feature_set", values="PR_AUC").round(3)
        if {"conventional", "drift_enhanced"} <= set(pv.columns):
            pv["difference (drift − conventional)"] = (pv["drift_enhanced"] - pv["conventional"]).round(3)
        st.dataframe(pv, use_container_width=True)
        st.info("The comparison is the experiment: neutral or negative differences are reported as measured.")
    with st.expander("Data quality checks"):
        st.json(dq)

# ------------------------------------------------------------------ 2. BEHAVIOUR & DRIFT
elif section == "Behaviour & Drift":
    st.title("Behaviour & Drift")
    drift = need(csv("drift_features.csv", parse_dates=["date"]), "Drift features not found.")
    st.caption(f"Personal baseline = mean/SD of the customer's own previous {C.BASELINE_DAYS} days (past only). "
               f"Warning = EWMA(z, span {C.CUSTOMER_EWMA_SPAN}) beyond ±{C.DRIFT_EWMA_THRESH} for ≥ {C.PERSIST_DAYS} consecutive days.")
    share = drift.groupby("date").agg(decline=("drift_direction", lambda x: (x < 0).mean()), increase=("drift_direction", lambda x: (x > 0).mean())).reset_index()
    fig = px.line(share, x="date", y=["decline", "increase"], title="Share of customers with a sustained drift warning",
                  labels={"value": "share of customers", "variable": ""}, color_discrete_map={"decline": "#d1343c", "increase": "#14915b"})
    fig.update_yaxes(tickformat=".0%"); st.plotly_chart(fig, use_container_width=True)

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
    f1 = go.Figure()
    f1.add_bar(x=days, y=x[0], name="Daily events", marker_color="#b9c6e4")
    f1.add_scatter(x=days, y=r["mu"][0], name="Personal baseline (past 28d mean)", line=dict(color="#12284c"))
    wd = np.where(r["direction"][0] < 0)[0]
    f1.add_scatter(x=days[wd], y=r["mu"][0][wd], mode="markers", name="Decline warning", marker=dict(color="#d1343c", size=7))
    f1.update_layout(title=f"Customer {pick}: activity vs personal baseline", height=360, legend_orientation="h")
    st.plotly_chart(f1, use_container_width=True)
    f2 = go.Figure()
    f2.add_scatter(x=days, y=r["z"][0], name="Z-score", line=dict(color="#b9c6e4"))
    f2.add_scatter(x=days, y=r["ewma"][0], name="EWMA of Z", line=dict(color="#2f6fed", width=3))
    f2.add_hline(y=-C.DRIFT_EWMA_THRESH, line_dash="dash", line_color="#d1343c"); f2.add_hline(y=C.DRIFT_EWMA_THRESH, line_dash="dash", line_color="#14915b")
    f2.update_layout(title="Z-score, EWMA and thresholds", height=320, legend_orientation="h")
    st.plotly_chart(f2, use_container_width=True)
    st.caption("Days before enough personal history exist are not scored (insufficient-history policy).")

# ------------------------------------------------------------------ 3. PREDICTION & EXPLANATION
elif section == "Prediction & Explanation":
    st.title("Prediction & Explanation")
    met = need(table("model_metrics.csv"), "Model metrics not found.")
    ex = jload("experiment_summary.json")
    st.subheader("Conventional vs drift-enhanced models")
    st.caption(f"Target: inactive_30d = no activity in the next 30 days (positive class). Threshold {ex['threshold']}. "
               "Both feature sets are scored on identical chronological test observations.")
    show = met[["model_name", "feature_set", "Precision", "Recall", "F1", "PR_AUC", "ROC_AUC", "positive_rate", "n"]].round(3)
    st.dataframe(show, use_container_width=True, hide_index=True)
    m = st.selectbox("Metric", ["PR_AUC", "ROC_AUC", "F1", "Precision", "Recall"])
    st.plotly_chart(px.bar(met, x="model_name", y=m, color="feature_set", barmode="group",
                           color_discrete_map={"conventional": "#8a94a9", "drift_enhanced": "#2f6fed"}), use_container_width=True)
    lt = ex["warning_lead_time"]
    st.subheader("Warning lead time")
    st.markdown(f"Customers with a complete inactivity episode: **{lt['customers_with_inactivity_episode']:,}** · warned by drift: **{lt['customers_warned']:,}** "
                f"({lt['share_warned']:.0%}) · median lead over the '30 days silent' rule: **{lt['median_lead_days']:.0f} days**.")
    st.caption("Lead time = (last activity + 30 days) − first sustained-decline warning. Resolution equals the observation grid.")
    st.subheader("Predicted inactivity risk (newest observation date)")
    sc = csv("scoring_predictions.csv")
    if sc is not None:
        st.plotly_chart(px.histogram(sc, x="predicted_probability", nbins=30, title=f"Distribution of predicted probabilities ({ex['best_drift_enhanced_model']})"), use_container_width=True)
        st.caption("Probabilities are model estimates; do not read an individual score as certainty.")
    st.subheader("SHAP explanation")
    g, l = C.FIGS / "shap_global.png", C.FIGS / "shap_local.png"
    if g.exists() and l.exists():
        c1, c2 = st.columns(2); c1.image(str(g), caption="Global: which features drive the model output"); c2.image(str(l), caption="One local example")
        st.caption("SHAP describes how the model uses features; it does not show causes of inactivity.")
    else:
        st.info("SHAP figures not found. Install shap and run `python -m src.insights.explain`.")

# ------------------------------------------------------------------ 4. SEGMENTS & VALUE PRIORITY
else:
    st.title("Segments & Value Priority")
    summ = need(table("segment_summary.csv"), "Segment summary not found.")
    st.subheader("K-Means engagement segments")
    c1, c2 = st.columns([1, 1])
    c1.plotly_chart(px.pie(summ, names="segment_name", values="customers", hole=.45), use_container_width=True)
    c2.dataframe(summ, use_container_width=True, hide_index=True)
    val = csv("customer_value.csv")
    if val is None:
        st.warning("No reliable value data: value proxy not created. Ranking uses risk only.")
    else:
        st.subheader("Historical value proxy")
        st.caption("Sum of purchased products' price bucket — a relative index, not currency and not predicted lifetime value.")
        st.plotly_chart(px.histogram(val[val.historical_value_proxy > 0], x="historical_value_proxy", nbins=40, log_y=True), use_container_width=True)
    st.subheader("Risk priority list")
    rp = csv("risk_priority.csv")
    if rp is not None:
        st.caption("Rule: priority_score = predicted inactivity probability × value percentile (newest observation date).")
        tier = st.multiselect("Action tier", ["Act now", "Monitor closely", "Routine"], default=["Act now"])
        n = st.slider("Rows", 10, 200, 25)
        view = rp[rp["action_tier"].isin(tier)].head(n)
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.download_button("Download full priority list (CSV)", rp.to_csv(index=False), "risk_priority.csv")
