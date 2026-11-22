"""Chunked readers so the 2 GB page_visit file never has to fit in RAM."""
import sys
from pathlib import Path
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C


def _resolve(name):
    p = C.DATA_DIR / C.FILES[name]
    if p.exists():
        return p
    csv = p.with_suffix(".csv")          # used only by the bundled demo generator
    if csv.exists():
        return csv
    raise FileNotFoundError(f"{p} not found. Set DRIFTEX_DATA_DIR to your Synerise folder.")


def columns_of(name):
    p = _resolve(name)
    if p.suffix == ".parquet":
        import pyarrow.parquet as pq
        return pq.ParquetFile(p).schema.names
    return list(pd.read_csv(p, nrows=0).columns)


def iter_chunks(name, columns=None):
    p = _resolve(name)
    if p.suffix == ".parquet":
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(p)
        for b in pf.iter_batches(batch_size=C.CHUNK_ROWS, columns=columns):
            yield b.to_pandas()
    else:
        for df in pd.read_csv(p, usecols=columns, chunksize=C.CHUNK_ROWS):
            yield df


def read_all(name, columns=None):
    return pd.concat(list(iter_chunks(name, columns)), ignore_index=True)


def day_of(series):
    return pd.to_datetime(series).dt.floor("D")
