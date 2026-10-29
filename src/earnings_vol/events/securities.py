# =============================================================================
# securities.py — `security` and `ticker_alias` (data model §3.1, §3.2), and
# resolving a source ticker to its security.
#
# A company keeps one security_id (its ticker at study build, e.g. META) for
# its whole history. A source row carries the ticker of its own day (FB until
# 2022-06-08), so every calendar, EPS and option row is resolved through
# ticker_alias before it is joined (ADR 0002 §4).
# =============================================================================

from datetime import date

import pandas as pd


def build_security(selection: pd.DataFrame) -> pd.DataFrame:
    """The `security` table, from universe.select_universe().

    The selection's universe_rank (a Yahoo market-cap rank) is left out: it
    stays in the local cache/universe.parquet (data model §2.1).
    """
    cols = ["security_id", "name", "gics_sector", "gics_sub_industry", "cik", "in_universe", "cboe_vx_index"]
    out = selection[cols].copy()
    out["in_universe"] = out["in_universe"].astype(bool)
    for c in ("cik", "cboe_vx_index"):
        out[c] = pd.Series([None if pd.isna(v) else str(v) for v in out[c]], dtype=object, index=out.index)
    return out.sort_values("security_id", kind="mergesort").reset_index(drop=True)


def build_ticker_alias(rows: list[dict]) -> pd.DataFrame:
    """The `ticker_alias` table from ingest.universe.alias_rows(), which the
    stage shell (events/run.py) passes in: a pure middle module imports no
    ingest module (ADR 0001 §1, tests/test_layering.py)."""
    return pd.DataFrame(rows, columns=["ticker", "valid_from", "valid_to", "security_id"]) \
        .sort_values(["ticker", "valid_from"], kind="mergesort").reset_index(drop=True)


def resolve_on(ticker: str, day: date, aliases: pd.DataFrame) -> str | None:
    """The security that `ticker` named on `day`, or None.

    Used for calendar rows, which carry the ticker of their own day.
    """
    hit = aliases[(aliases["ticker"] == ticker) & (aliases["valid_from"] <= day)
                  & (aliases["valid_to"].isna() | (aliases["valid_to"].map(lambda v: v is not None and v >= day)))]
    if len(hit) > 1:
        raise ValueError(f"{ticker} on {day} matches {len(hit)} aliases")
    return None if hit.empty else hit["security_id"].iloc[0]


def resolve_any(ticker: str, aliases: pd.DataFrame) -> str | None:
    """The security a ticker ever named, ignoring dates.

    Used for eps_history, where DoltHub copied FB's quarters under META too,
    so a META row can be dated before META existed. Refuses a ticker that two
    securities used at different times.
    """
    ids = set(aliases.loc[aliases["ticker"] == ticker, "security_id"])
    if len(ids) > 1:
        raise ValueError(f"{ticker} was used by {sorted(ids)}: resolve it by date")
    return next(iter(ids), None)
