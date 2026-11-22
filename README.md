# DRIFTEX
**Machine Learning System for Personalised Behaviour Change Detection and Inactivity Forecasting** — Synerise e-commerce dataset (Aastha & Shaffy).

Research question: do individual behavioural-drift signals warn of inactivity earlier / better than conventional churn features?
The comparison is the experiment: results are reported as measured, including neutral or negative ones.

## Setup and run
```bash
pip install -r requirements.txt
# put the six Synerise parquet files in data/raw/   (or: export DRIFTEX_DATA_DIR=/path/to/files)
python run_all.py                       # full pipeline, ~ minutes on real data
streamlit run src/dashboard/app.py      # main dashboard (4 sections)
pytest                                   # tests
```
No data yet? `python make_demo_data.py` creates a synthetic Synerise-like demo (test-only, never report its results),
then `export DRIFTEX_DATA_DIR=demo_data DRIFTEX_SAMPLE_PCT=100` before `python run_all.py`.
Use `DRIFTEX_SAMPLE_PCT=100` for all customers (needs more RAM); default is a reproducible 10 % customer sample.

## Plan coverage
| Plan item | Where |
|---|---|
| Customer-day aggregation, cleaning checks | `src/drift/activity.py` |
| Rolling personal baseline (past only) | `src/drift/baseline.py` |
| Z-score, EWMA, persistence drift warning | `src/drift/detect.py`, `run_drift.py` → `drift_features.csv` |
| 30-day inactivity labels, incomplete follow-up excluded | `src/prediction/labels.py` |
| Past-only features | `src/prediction/features.py` |
| Logistic Regression / Random Forest / XGBoost, one pipeline, train-only preprocessing | `src/prediction/train.py` |
| Precision, Recall, F1, PR-AUC, ROC-AUC, warning lead time | `src/prediction/evaluate.py` |
| Conventional vs drift-enhanced on identical test rows | `train.py` → `model_metrics.csv` |
| K-Means segmentation | `src/insights/segments.py` |
| Historical value proxy (not CLV) | `src/insights/value_proxy.py` |
| SHAP global + local example | `src/insights/explain.py` |
| Risk prioritisation | `src/insights/risk_priority.py` |
| Streamlit dashboard: Overview · Behaviour & Drift · Prediction & Explanation · Segments & Value Priority | `src/dashboard/app.py` |
| Tests | `tests/` |
| Data dictionary, experiment notes | `docs/` |

## Extension: Product Interest Intelligence (optional, separate dashboard)
Per-product interest rising/declining, forecasts, alerts, live replay, categories. `run_all.py` also builds its tables.
```bash
python app/server.py     # http://localhost:8000  (Chart.js loaded from CDN, needs internet)
```
This extension goes beyond the plan's scope (the plan excludes real-time streaming; the "Live Monitor" is a historical replay).
Present it as an extension or leave it out.

## Honest notes for the report
* Synerise `page_visit` has no product id; price is a quantised bucket; names and queries are anonymised.
* Value proxy = relative purchase-value index from price buckets, not currency and not predicted CLV.
* SHAP explains model output, not causality. Thresholds are simple documented defaults (`config.py`), not tuned on test data.
* Verify column names against your files (`config.py`) and dataset licence/citation before submission.

## Repository layout
```
config.py  run_all.py  make_demo_data.py  requirements.txt
data/raw  data/processed   docs/   outputs/figures  outputs/tables
src/drift/  src/prediction/  src/insights/  src/dashboard/app.py   tests/
pipeline/ + app/            (product-interest extension)
```
Git workflow from the plan: `feature/shaffy-drift-detection`, `feature/aastha-inactivity-forecasting`, PRs into `main` after tests.
