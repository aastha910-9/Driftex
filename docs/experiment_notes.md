# Experiment notes

## Drift logic (Shaffy)
1. Daily activity per customer (events/day, zeros on silent days) after the customer's first activity.
2. Personal baseline at day t = mean and SD of the customer's own previous 28 days (days t-28 ... t-1, **never t or later**).
   Needs >= 14 past days, otherwise not scored.
3. Z-score = (x_t - mean) / (SD + 0.5), clipped to ±5.
4. EWMA of the Z-score, span 7.
5. Persistence rule: |EWMA| >= 0.5 in the same direction for >= 5 consecutive days => `drift_flag = 1`
   (`drift_direction = -1` sustained decline, `+1` sustained increase).
All thresholds are in `config.py`. They are agreed, simple defaults and were NOT tuned on test data.

## Prediction design (Aastha)
* Target: `inactive_30d`; positive class = inactive. Threshold 0.5 (reported).
* Chronological split: last 25 % of observation dates = test; training dates end 30 days before the test start.
* Preprocessing (median imputation, scaling) is inside the sklearn Pipeline and fitted on training rows only.
* Imbalance: class weights / scale_pos_weight; metrics reported: Precision, Recall, F1, PR-AUC, ROC-AUC.
* Conventional vs drift-enhanced: identical rows, identical split. Drift-enhanced = conventional + 5 drift columns.
* The model explained/scored is chosen by a fixed rule: best PR-AUC among drift-enhanced models.
* Warning lead time: (last activity + 30 days) - first sustained-decline warning, for customers with a complete inactivity
  episode. Compares drift warning with the "30 days silent" rule. Resolution = 7 days.

## Segmentation and value (Shaffy)
* K-Means features (6): active_days, events_per_active_day, buys_total, carts_total, searches_total, recency_days.
  Counts are log1p-transformed, then standard-scaled. k is chosen from 3-6 by silhouette on a subsample.
* Segments are named from observed patterns (engagement rank; "(lapsing)" if average recency > 28 days).
* Value proxy = sum of purchased products' price bucket (relative index, not currency, not predicted CLV).
* Risk priority = predicted inactivity probability x value percentile (probability only if no value data).

## Known limitations
* Demo-data results are not research results; run on the real files before reporting anything.
* Customer sample (hash-based) rather than all customers, for memory reasons; set DRIFTEX_SAMPLE_PCT=100 to use all.
* Price is a quantised bucket, so the value proxy is a relative index.
* Product names and search text are anonymised; page_visit has no product id.
* Prices, stock, promotions, seasonality are not in the data and are not modelled.
* SHAP explains the model, not causal reasons. Historical value proxy is not predicted CLV.
* Do not assume drift features help: the comparison is the experiment.
