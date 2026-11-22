"""
Generates a SMALL synthetic dataset with the SAME schema as the Synerise
RecSys-Challenge-2025 files, so the whole system can be tested before you
run it on the real 2-GB files.   python make_demo_data.py
"""
import numpy as np, pandas as pd
from pathlib import Path

rng = np.random.default_rng(7)
OUT = Path(__file__).resolve().parent / "demo_data"
OUT.mkdir(exist_ok=True)

N_SKU, N_CLIENT, N_DAYS = 800, 30000, 126
start = pd.Timestamp("2022-10-03")
days = pd.date_range(start, periods=N_DAYS)

# product popularity + trend archetypes
base = rng.lognormal(0.5, 0.9, N_SKU)
kind = rng.choice(["flat", "rise", "fall", "spike", "season"], N_SKU, p=[.45, .17, .17, .08, .13])
t = np.arange(N_DAYS)
curve = np.ones((N_SKU, N_DAYS))
for i, k in enumerate(kind):
    if k == "rise":   curve[i] = 0.5 + 1.8 * (t / N_DAYS) ** 1.5
    if k == "fall":   curve[i] = 1.9 - 1.5 * (t / N_DAYS) ** 1.2
    if k == "spike":  c = rng.integers(60, N_DAYS - 10); curve[i] = 1 + 5 * np.exp(-((t - c) ** 2) / 60)
    if k == "season": curve[i] = 1 + 0.6 * np.sin(2 * np.pi * (t + rng.integers(0, 30)) / 28)
weekday = 1 + 0.18 * np.sin(2 * np.pi * t / 7)
traffic = 1 + 0.25 * np.sin(2 * np.pi * t / 63) + 0.003 * t
lam = base[:, None] * curve * weekday[None] * traffic[None]

# customer behaviour: individual rates, some customers fade out (drift) then churn
crate = rng.gamma(1.2, 1.0, N_CLIENT) + 0.05
churn = rng.random(N_CLIENT) < 0.35
cday = rng.integers(40, N_DAYS - 5, N_CLIENT)
alive = np.ones((N_DAYS, N_CLIENT), dtype=np.float32)
for c in np.nonzero(churn)[0]:
    fade = np.clip(1 - (t - (cday[c] - 14)) / 14, 0, 1)
    alive[:, c] = fade
joined = rng.integers(0, 30, N_CLIENT)
alive[t[:, None] < joined[None, :]] = 0
W = alive * crate[None, :]
W = W / W.sum(1, keepdims=True)

def assign_clients(day_idx):
    out = np.empty(len(day_idx), dtype=np.int64)
    for d in np.unique(day_idx):
        m = day_idx == d
        out[m] = rng.choice(N_CLIENT, size=m.sum(), p=W[d])
    return out

def events(mult):
    cnt = rng.poisson(lam * mult)
    si, di = np.nonzero(cnt)
    rep = cnt[si, di]
    s = np.repeat(si, rep); d = np.repeat(di, rep)
    ts = days[d] + pd.to_timedelta(rng.integers(0, 86400, len(d)), unit="s")
    return pd.DataFrame({"client_id": assign_clients(d), "timestamp": ts, "sku": s})

cart = events(2.2); buy = events(0.55); rem = events(0.7)
pv_n = int(lam.sum() * 6)
d = rng.choice(N_DAYS, pv_n, p=(traffic * weekday) / (traffic * weekday).sum())
pv = pd.DataFrame({"client_id": assign_clients(d),
                   "timestamp": days[d] + pd.to_timedelta(rng.integers(0, 86400, pv_n), unit="s"),
                   "url": rng.integers(0, 4000, pv_n)})
sq_n = int(pv_n * .12)
d = rng.choice(N_DAYS, sq_n, p=(traffic * weekday) / (traffic * weekday).sum())
sq = pd.DataFrame({"client_id": assign_clients(d),
                   "timestamp": days[d] + pd.to_timedelta(rng.integers(0, 86400, sq_n), unit="s"),
                   "query": ["[" + ",".join(map(str, rng.integers(0, 255, 16))) + "]" for _ in range(sq_n)]})
props = pd.DataFrame({"sku": np.arange(N_SKU), "category": rng.integers(0, 40, N_SKU),
                      "price": rng.integers(0, 100, N_SKU),
                      "name": ["[" + ",".join(map(str, rng.integers(0, 255, 16))) + "]" for _ in range(N_SKU)]})

tables = {"add_to_cart": cart, "product_buy": buy, "remove_from_cart": rem,
          "page_visit": pv, "search_query": sq, "product_properties": props}
try:
    import pyarrow  # noqa
    for n, df in tables.items(): df.to_parquet(OUT / f"{n}.parquet", index=False)
    print("wrote parquet demo files")
except ImportError:
    for n, df in tables.items(): df.to_csv(OUT / f"{n}.csv", index=False)
    print("pyarrow missing -> wrote csv demo files")
print({k: len(v) for k, v in tables.items()})
