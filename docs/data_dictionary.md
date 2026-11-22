# Data dictionary

## Raw Synerise files (data/raw/)
| File | Columns used | Meaning |
|---|---|---|
| page_visit | client_id, timestamp, url | Page view of an (anonymised) URL. **No product id.** |
| search_query | client_id, timestamp | Search event (query text is an anonymised vector, not used) |
| add_to_cart | client_id, timestamp, sku | Product added to cart |
| remove_from_cart | client_id, timestamp, sku | Product removed from cart |
| product_buy | client_id, timestamp, sku | Product purchased |
| product_properties | sku, category, price | `price` is a **quantised bucket (0-99)**, not currency; `name` is an anonymised vector |

Column names are configured in `config.py`. Verify them against your files before running (Day-1 audit).

## Definitions
* **Qualifying activity**: any event in the five event files (visit, search, cart add/remove, purchase).
* **Daily activity measure**: `events` = total qualifying events of a customer on a date.
* **Customer sample**: customers with `client_id % 100 < CUSTOMER_SAMPLE_PCT` (default 10 %), reproducible.
* **Observation dates**: every `OBS_STEP_DAYS` (7) days, anchored on the last data day.
* **Eligible observation**: at least `MIN_HISTORY_DAYS` (14) since first activity AND active in the last 28 days.
* **inactive_30d**: 1 if no qualifying activity in (t, t+30 days]; observations with an incomplete 30-day future are excluded.

## Output tables (data/processed/) - join key: customer_id + date / observation_date (ISO yyyy-mm-dd, dates are calendar days of the event timestamp, no timezone conversion)
| File | Owner | Columns |
|---|---|---|
| customer_daily_activity.csv | Shaffy | customer_id, date, visits, searches, carts, removes, buys, events, buy_value |
| drift_features.csv | Shaffy | customer_id, date, drift_zscore, drift_ewma, drift_flag, drift_level, drift_direction, drift_run_days |
| customer_segments.csv | Shaffy | customer_id, segment_id, segment_name, active_days, events_total, events_per_active_day, buys_total, recency_days |
| customer_value.csv | Shaffy | customer_id, historical_value_proxy, purchases, value_percentile, value_tier, formula |
| inactivity_labels.csv | Aastha | customer_id, observation_date, inactive_30d |
| model_features.csv | Aastha | customer_id, observation_date + 14 past-only predictors |
| model_metrics.csv | Aastha | model_name, feature_set, split, Precision, Recall, F1, PR_AUC, ROC_AUC, positive_rate, threshold, n |
| predictions.csv | Aastha | customer_id, observation_date, model_name, feature_set, inactive_30d, predicted_probability, predicted_class (test period) |
| scoring_predictions.csv | Aastha | predictions for the newest date (no label needed) |
| risk_priority.csv | shared | scoring predictions + value + segment + priority_score, priority_rank, action_tier |

Missing values: drift columns are absent (row not exported) while history is insufficient; model imputers use the training median.
Duplicates: exact duplicate raw event rows are dropped per chunk; customer_id + date is unique after aggregation (asserted).

## Product-interest extension (optional HTML dashboard)
daily_product.csv, daily_company.csv, products.csv, daily_top.csv, weekly_top.csv, forecast.csv, product_stats.csv, alerts.csv, model_report.json.
