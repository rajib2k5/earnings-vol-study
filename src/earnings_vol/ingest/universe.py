# =============================================================================
# universe.py — Which companies the study covers, and why.
#
# THE RULE (params.yaml, section universe)
#   1. Start from the current S&P 500 constituents (one Wikipedia revision).
#   2. Keep one share class per company (drop GOOG, BRK.A, FOX, NWS).
#   3. A company is eligible when DoltHub has calendar rows for it from the
#      daily-snapshot era on, and option snapshots on the last data date.
#   4. Rank the eligible companies by Yahoo market cap on the rank date.
#      in_universe = rank <= n_largest, or the company has a CBOE VX* index.
#
# SURVIVORSHIP BIAS (stated, not removed)
#   The rank uses today's index membership and today's market caps. Companies
#   that shrank, were acquired or left the S&P 500 between 2020 and today are
#   missing, and companies that grew into the top 50 (often because their
#   stock rose) are in it for their whole history. So the sample over-weights
#   firms that did well after 2020. The primary (daily) sample starts only
#   about two years before the rank date, which limits, but does not remove,
#   the bias. Every result page states this.
#
# LICENCE
#   The rank comes from Yahoo market caps. in_universe, an in/out label, is
#   class F and committed (data model §2.1). universe_rank, a per-row
#   Yahoo-derived number for ~500 firms, stays in the local selection
#   (cache/universe.parquet) and is not a column of `security` (milestone-1
#   review). The market caps themselves stay in raw_dir(), never committed.
# =============================================================================

from datetime import date

import pandas as pd

# GOOGL's index is VXGOG, built on GOOG (data model §3.1).
VX_INDEX = {"AAPL": "VXAPL", "AMZN": "VXAZN", "GOOGL": "VXGOG", "GS": "VXGS", "IBM": "VXIBM"}


# The study's horizon starts here (the session table, data model §3.3). A
# ticker without a known change is asserted valid from this day on; earlier
# history is not checked.
HORIZON_START = date(2016, 1, 1)

# Ticker changes inside the data (ADR 0002 §4). Each entry is an older ticker
# of a security: (old ticker, first day, last day). The current ticker is
# valid from the day after the last old one. Found by checking every universe
# company's calendar and EPS history for a late start (milestone 1).
KNOWN_RENAMES = {
    "META": [("FB", date(2012, 5, 18), date(2022, 6, 8))],
    # United Technologies became RTX (Raytheon Technologies) on 2020-04-03; the
    # calendar has one UTX row (2020-01-28) and eps_history has UTX and RTX
    # rows for the 2019 quarters.
    "RTX": [("UTX", HORIZON_START, date(2020, 4, 2))],
}


def alias_rows(security_ids: list[str]) -> list[dict]:
    """The ticker_alias rows (data model §3.2) of the given securities."""
    rows = []
    for sid in sorted(security_ids):
        start = HORIZON_START
        for old, first, last in KNOWN_RENAMES.get(sid, []):
            rows.append({"ticker": old, "valid_from": first, "valid_to": last, "security_id": sid})
            start = date.fromordinal(last.toordinal() + 1)
        rows.append({"ticker": sid, "valid_from": start, "valid_to": None, "security_id": sid})
    return rows


def source_tickers(security_ids: list[str]) -> list[str]:
    """Every act_symbol to read from DoltHub for these securities, old names included."""
    return sorted({r["ticker"] for r in alias_rows(security_ids)})


def yahoo_symbol(ticker: str) -> str:
    """DoltHub and Wikipedia write BRK.B; Yahoo writes BRK-B."""
    return ticker.replace(".", "-")


def fetch_market_caps(symbols: list[str]) -> pd.DataFrame:
    """Yahoo market cap now, one request per symbol (network; not used in tests)."""
    import yfinance as yf  # imported here so the pure functions need no network library

    rows = []
    for s in symbols:
        try:
            cap = float(yf.Ticker(yahoo_symbol(s)).fast_info["marketCap"])
        except Exception as exc:  # a missing quote is recorded, not fatal
            rows.append({"symbol": s, "market_cap_yf": None, "error": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        rows.append({"symbol": s, "market_cap_yf": cap, "error": None})
    return pd.DataFrame(rows, columns=["symbol", "market_cap_yf", "error"])


def select_universe(constituents: pd.DataFrame, caps: pd.DataFrame, eligible: set[str],
                    *, n_largest: int, force_include: list[str], drop_share_classes: list[str]) -> pd.DataFrame:
    """Apply the rule above. Pure: every input is passed in.

    Returns one row per kept constituent with the columns of the `security`
    table: security_id, name, gics_sector, gics_sub_industry, cik,
    in_universe, universe_rank, cboe_vx_index.
    """
    df = constituents[~constituents["symbol"].isin(drop_share_classes)].copy()
    df = df.merge(caps[["symbol", "market_cap_yf"]], on="symbol", how="left")
    ok = df["symbol"].isin(eligible) & df["market_cap_yf"].notna()
    # Largest first; equal caps are ordered by symbol, so the rank is deterministic.
    ranked = df[ok].sort_values(["market_cap_yf", "symbol"], ascending=[False, True], kind="mergesort")
    rank = {s: i + 1 for i, s in enumerate(ranked["symbol"])}
    # dtype=object keeps the ranks as ints next to the None of unranked rows
    # (a plain column would turn them into floats).
    df["universe_rank"] = pd.Series([rank.get(s) for s in df["symbol"]], dtype=object, index=df.index)
    missing = [s for s in force_include if s not in rank]
    if missing:
        raise ValueError(f"force_include names are not eligible: {missing}")
    df["in_universe"] = [r is not None and (r <= n_largest or s in force_include)
                         for s, r in zip(df["symbol"], df["universe_rank"])]
    df["cboe_vx_index"] = [VX_INDEX.get(s) for s in df["symbol"]]
    out = df.rename(columns={"symbol": "security_id"})
    out = out.sort_values("security_id", kind="mergesort").reset_index(drop=True)
    return out[["security_id", "name", "gics_sector", "gics_sub_industry", "cik",
                "in_universe", "universe_rank", "cboe_vx_index"]]
