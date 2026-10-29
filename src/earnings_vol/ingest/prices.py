# =============================================================================
# prices.py — Yahoo daily prices via yfinance. LOCAL ONLY, never committed.
#
# Saved as raw_dir()/yfinance/<yahoo symbol>.parquet with the columns
#   date, open, high, low, close, volume, dividends, splits
# from yfinance's history(auto_adjust=False, actions=True):
#   - open/high/low/close are adjusted for SPLITS (Yahoo always does this) but
#     NOT for dividends;
#   - dividends is the cash amount on its ex-date (split-adjusted like the
#     prices); splits is the ratio on the split date (2.0 for 2-for-1), else 0.
#
# Two uses at milestone 1, both local (ADR 0002 §3; data model §3.9):
#   1. the overnight-gap diagnostic, which needs open and close;
#   2. the "snapshot is the close" check, which needs the AS-OF close: the
#      close a trader saw that day, before any later split. asof_close() undoes
#      the later splits.
# =============================================================================

import time
from pathlib import Path

import pandas as pd

START = "2019-06-01"
END = "2026-10-29"   # exclusive in yfinance: the last row is 2026-10-28


def download(symbol: str, out_dir: Path) -> pd.DataFrame:
    import yfinance as yf  # network library, imported only where it is used

    hist = yf.Ticker(symbol).history(start=START, end=END, auto_adjust=False, actions=True)
    if hist.empty:
        raise RuntimeError(f"yfinance returned no rows for {symbol}")
    df = pd.DataFrame({
        "date": [d.date() for d in hist.index],
        "open": hist["Open"].astype("float64").to_numpy(),
        "high": hist["High"].astype("float64").to_numpy(),
        "low": hist["Low"].astype("float64").to_numpy(),
        "close": hist["Close"].astype("float64").to_numpy(),
        "volume": hist["Volume"].astype("float64").to_numpy(),
        "dividends": hist["Dividends"].astype("float64").to_numpy(),
        "splits": hist["Stock Splits"].astype("float64").to_numpy(),
    })
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / f"{symbol}.parquet", index=False)
    return df


def download_all(symbols: list[str], out_dir: Path, pause: float = 0.3) -> dict:
    out = {}
    for s in symbols:
        t0 = time.perf_counter()
        df = download(s, out_dir)
        out[s] = {"rows": len(df), "first": str(df["date"].iloc[0]), "last": str(df["date"].iloc[-1]),
                  "seconds": round(time.perf_counter() - t0, 2)}
        time.sleep(pause)
    return out


def load(symbol: str, raw_dir: Path) -> pd.DataFrame:
    return pd.read_parquet(raw_dir / "yfinance" / f"{symbol}.parquet")


def split_factor_after(df: pd.DataFrame) -> pd.Series:
    """For each row, the product of the split ratios on LATER dates.

    Yahoo divides every price before a 10-for-1 split by 10. Multiplying by
    this factor gives back the price as it was quoted that day. Example: with
    one 10-for-1 split on day 3, rows 1 and 2 get 10 and rows 3 onward get 1.
    """
    ratio = df["splits"].where(df["splits"] > 0, 1.0).to_numpy()
    # Product over rows strictly after each row: reverse cumulative product,
    # shifted by one.
    after = pd.Series(ratio[::-1]).cumprod()[::-1].to_numpy()
    after = list(after[1:]) + [1.0]
    return pd.Series(after, index=df.index, dtype="float64")


def asof_close(df: pd.DataFrame) -> pd.Series:
    """The close as quoted on its own day, before later splits."""
    return df["close"] * split_factor_after(df)
