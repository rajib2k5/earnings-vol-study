# =============================================================================
# cboe.py — Download Cboe's single-stock volatility indices (VX*) as CSV.
#
# Run:  uv run python -m earnings_vol.ingest.cboe          (the five files)
#
# WHAT AND WHY (ADR 0003, "Validation plan (milestone 2)", item 1)
#   VXAPL, VXAZN, VXGOG, VXGS and VXIBM are VIX-method 30-day indices on five
#   stocks of the universe (universe.VX_INDEX). The cross-check compares them
#   with our cm30_blind_iv (docs/validation/vx-preregistration.md). Cboe
#   publishes each one at
#     https://cdn.cboe.com/api/global/us_indices/daily_prices/<SYM>_History.csv
#   which answers with a 307 redirect; requests follows it.
#
# WHERE THE FILES GO
#   raw_dir()/cboe/<SYM>.csv, exactly as downloaded, so a re-run reads them
#   again without the network. parse_history() turns one into a table.
#
# THE REQUEST BUDGET
#   One request per symbol, at most MAX_RETRIES more after a network error, a
#   429 or a 5xx; any other HTTP error stops at once. The User-Agent names the
#   project and its public repository only: no e-mail address, no personal
#   contact, in a header or anywhere else.
#
# LICENCE (data model §1.3, ADR 0001 §7)
#   Cboe data. The files stay on this machine (raw/ is never committed;
#   tools/licensing/check_data_files.py refuses a tracked copy of one). Only
#   aggregate statistics of the comparison are committed
#   (data/derived/vx_crosscheck.json).
# =============================================================================

import hashlib
import io
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests

URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{symbol}_History.csv"
SYMBOLS = ("VXAPL", "VXAZN", "VXGOG", "VXGS", "VXIBM")
USER_AGENT = "earnings-vol-study/0.5 (research; +https://github.com/rajib2k5/earnings-vol-study)"
MAX_RETRIES = 2
RETRY_WAIT_SECONDS = (5.0, 15.0)
TIMEOUT_SECONDS = 60


def url(symbol: str) -> str:
    """The Cboe CSV address of one of the five symbols (any other is refused)."""
    if symbol not in SYMBOLS:
        raise ValueError(f"{symbol!r} is not one of the five VX* indices {SYMBOLS}")
    return URL.format(symbol=symbol)


def _retryable(resp: requests.Response | None) -> bool:
    return resp is None or resp.status_code == 429 or resp.status_code >= 500


def fetch(symbol: str, session: requests.Session | None = None, sleep=time.sleep) -> tuple[bytes, dict]:
    """(body, record) of one symbol: one GET, plus at most MAX_RETRIES retries.

    The record says how many attempts were made, the HTTP status of each hop
    (the 307 and the final 200) and the final address.
    """
    s = session or requests.Session()
    attempts, last_error = 0, None
    for attempt in range(1 + MAX_RETRIES):
        attempts += 1
        resp = None
        try:
            resp = s.get(url(symbol), headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS,
                         allow_redirects=True)
            if resp.status_code == 200:
                return resp.content, {"attempts": attempts,
                                      "hops": [r.status_code for r in resp.history] + [resp.status_code],
                                      "final_url": resp.url}
            last_error = f"HTTP {resp.status_code}"
        except requests.RequestException as e:   # a network error: retried
            last_error = f"{type(e).__name__}: {e}"
        if not _retryable(resp) or attempt == MAX_RETRIES:
            break
        sleep(RETRY_WAIT_SECONDS[attempt])
    raise RuntimeError(f"{symbol}: no file after {attempts} attempt(s): {last_error}")


def parse_history(text: str) -> pd.DataFrame:
    """Cboe history CSV text -> columns date (datetime.date) and close (float64, the index in vol points).

    The file has a DATE column (MM/DD/YYYY) and OPEN, HIGH, LOW, CLOSE. A
    second row for one date, a non-numeric close or a missing DATE/CLOSE
    column is an error: nothing is dropped or filled silently. A close of 0
    or below is kept (and later refused by the log change), not removed here.
    """
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    cols = {c.strip().upper(): c for c in df.columns}
    if "DATE" not in cols or "CLOSE" not in cols:
        raise ValueError(f"unexpected Cboe columns {list(df.columns)}")
    dates = []
    for d in df[cols["DATE"]]:
        d = d.strip()
        dates.append(date.fromisoformat(d) if "-" in d else datetime.strptime(d, "%m/%d/%Y").date())
    close = pd.to_numeric(df[cols["CLOSE"]].str.strip(), errors="raise").astype("float64")
    out = pd.DataFrame({"date": dates, "close": close})
    if out["date"].duplicated().any():
        raise ValueError(f"duplicate dates in a Cboe file: {sorted(set(out.loc[out['date'].duplicated(), 'date']))[:5]}")
    return out.sort_values("date", kind="mergesort").reset_index(drop=True)


def describe(path: Path) -> dict:
    """SHA-256, size, row count and first/last date of a downloaded file (for the ledger)."""
    raw = path.read_bytes()
    df = parse_history(raw.decode("utf-8"))
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "rows": len(df),
            "first": str(df["date"].iloc[0]), "last": str(df["date"].iloc[-1])}


def download_all(out_dir: Path, symbols=SYMBOLS, session: requests.Session | None = None, log=print) -> dict:
    """Fetch each symbol once (with its retries) into out_dir/<SYM>.csv; return one record per symbol."""
    out_dir.mkdir(parents=True, exist_ok=True)
    s = session or requests.Session()
    out = {}
    for sym in symbols:
        fetched_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        body, rec = fetch(sym, s)
        path = out_dir / f"{sym}.csv"
        path.write_bytes(body)
        out[sym] = {"fetched_utc": fetched_utc, **rec, **describe(path)}
        log(f"{sym}: {out[sym]['rows']} rows {out[sym]['first']}..{out[sym]['last']}, {out[sym]['bytes']} B, "
            f"attempts {rec['attempts']}, hops {rec['hops']}")
    return out


def load(symbol: str, raw: Path) -> pd.DataFrame:
    """The parsed local file of one symbol (no network)."""
    url(symbol)                                  # refuses a symbol that is not one of the five
    return parse_history((raw / f"{symbol}.csv").read_text())


def main() -> int:
    from earnings_vol import config

    out_dir = config.raw_dir() / "cboe"
    record = download_all(out_dir)
    (out_dir / "fetch_log.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print("wrote", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
