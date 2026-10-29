# =============================================================================
# fred.py — Download FRED series as CSV: DTB3 (3-month T-bill) and VIXCLS.
#
# FRED's public graph endpoint needs no API key. Each series is saved as
# raw_dir()/fred/<series>.csv exactly as downloaded, so a re-run can read it
# again without the network. parse_series() turns the file into a table.
#
# LICENCE (data model §1.3)
#   DTB3 is US-government data: class U, may be committed.
#   VIXCLS is a CBOE index that FRED republishes, so it is CBOE data: every
#   column made from it ends in _cboe and stays on this machine.
# =============================================================================

import io
from datetime import date
from pathlib import Path

import pandas as pd
import requests

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def download(series: str, out_dir: Path) -> Path:
    resp = requests.get(URL, params={"id": series}, timeout=60)
    resp.raise_for_status()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{series}.csv"
    path.write_bytes(resp.content)
    return path


def download_all(series: list[str], out_dir: Path) -> dict:
    out = {}
    for s in series:
        path = download(s, out_dir)
        out[s] = {"rows": len(parse_series(path.read_text(), s))}
    return out


def parse_series(text: str, series: str) -> pd.DataFrame:
    """CSV text -> columns date (datetime.date) and value (float64, NaN when FRED has none).

    FRED writes a missing day (a holiday, or a day the index was not
    published) as an empty field. It stays missing here: nothing is filled.
    """
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    date_col = df.columns[0]
    if series not in df.columns or date_col not in ("observation_date", "DATE"):
        raise ValueError(f"unexpected FRED columns {list(df.columns)} for {series}")
    values = pd.to_numeric(df[series].replace({"": None, ".": None}), errors="raise")
    return pd.DataFrame({"date": [date.fromisoformat(d) for d in df[date_col]],
                         "value": values.astype("float64")})
