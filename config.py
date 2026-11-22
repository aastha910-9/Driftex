"""
DRIFTEX - Product Interest Intelligence : central configuration.
Change DATA_DIR (or set env var DRIFTEX_DATA_DIR) to the folder that holds the
six Synerise parquet files.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DRIFTEX_DATA_DIR", ROOT / "demo_data"))
OUT_DIR = ROOT / "data" / "processed"        # every generated table lives here
TABLES = ROOT / "outputs" / "tables"
FIGS = ROOT / "outputs" / "figures"
MODELS = ROOT / "outputs" / "models"
for _d in (OUT_DIR, TABLES, FIGS, MODELS):
    _d.mkdir(parents=True, exist_ok=True)

# ---- raw file names (as in your screenshot) -------------------------------
FILES = {
    "page_visit": "page_visit.parquet",
    "search_query": "search_query.parquet",
    "add_to_cart": "add_to_cart.parquet",
    "remove_from_cart": "remove_from_cart.parquet",
    "product_buy": "product_buy.parquet",
    "product_properties": "product_properties.parquet",
}

# ---- column names (Synerise / RecSys Challenge 2025 schema) ----------------
# If your files use other names, change them here. Nothing else needs editing.
COL_CLIENT = "client_id"
COL_TS = "timestamp"
COL_SKU = "sku"
COL_URL = "url"          # page_visit has url (NOT sku) in the original dataset
COL_CATEGORY = "category"
COL_PRICE = "price"      # quantised price bucket (0-99) in the original dataset

# If your page_visit file ALSO has a product column, put its name here and
# page views become product-level automatically. None = company-level only.
PAGE_VISIT_SKU_COL = None   # auto-detected too if a column called "sku" exists

# ---- interest index --------------------------------------------------------
# Interest = w_views*views + w_carts*add_to_cart + w_buys*purchases
INTEREST_WEIGHTS = {"views": 1.0, "carts": 3.0, "buys": 5.0}

# ---- modelling ---------------------------------------------------------------
MAX_PRODUCTS = 3000          # top-N products by activity are modelled / shown
MIN_TOTAL_INTEREST = 30      # ignore very sparse products
CHUNK_ROWS = 2_000_000       # rows per chunk while reading big parquet files
CHANGE_THRESHOLD = 0.20      # +-20% vs recent 4-week average = Increasing / Decreasing
MIN_BASE_INTEREST = 8        # min avg weekly interest to be used as a training row
Z_ALERT = 3.0                # z-score above this = spike alert
Z_DROP = 2.2                 # z-score below -this = drop alert (drops are naturally bounded at 0)
EWMA_SPAN = 7
FORECAST_WEEKS = 4
RANDOM_STATE = 42

# ---- customer-level modules (drift, inactivity prediction, segments) -------
# The raw files hold millions of customers. We keep a reproducible hash-sample:
# customers with (client_id % 100) < CUSTOMER_SAMPLE_PCT. Use 100 for everyone.
CUSTOMER_SAMPLE_PCT = int(os.environ.get("DRIFTEX_SAMPLE_PCT", 10))
BASELINE_DAYS = 28           # rolling personal baseline window (past days only)
MIN_HISTORY_DAYS = 14        # days since first activity needed before drift is scored
SD_FLOOR = 0.5               # avoids huge z-scores for very regular customers
CUSTOMER_EWMA_SPAN = 7       # EWMA smoothing of the daily z-score
DRIFT_EWMA_THRESH = 0.5      # |EWMA of z| needed to count as a deviation
PERSIST_DAYS = 5             # deviation must persist this many consecutive days
OBS_STEP_DAYS = 7            # prediction / export observation dates every N days
INACTIVITY_HORIZON = 30      # inactive_30d : no activity in (t, t+30]
RECENT_ACTIVE_DAYS = 28      # eligible = active at least once in the last N days
TEST_FRACTION = 0.25         # last 25% of observation dates are the test period
DECISION_THRESHOLD = 0.5     # probability threshold for predicted_class
KMEANS_K_RANGE = (3, 4, 5, 6)
