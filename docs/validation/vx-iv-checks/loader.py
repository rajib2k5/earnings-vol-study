# =============================================================================
# loader.py - The phase-2 loader of the vx-iv-checks pre-registration
# (preregistration.md §3, gate G4). The only part of the phase-2 driver that
# is not frozen: it is written at the start of phase 2.
#
# Why it is outside probes/: every file in probes/ is hashed in
# probes/SHA256SUMS, and gate G2 stops on any change. The loader must change
# once (when it is written) and may change again for a fix that G4 forces,
# so it lives here. probes/phase2.py reads this file's bytes, records their
# SHA-256 in aggregate.json (G2), and runs those same bytes. Nothing checks
# the hash; it puts the loader that was actually used on record.
#
# When phase2.py runs this file, the clone's src and probes/ are already on
# sys.path (after phase2.py's import-path assertion), so the loader can
# import earnings_vol, synth and ivchecks. It computes no statistic.
#
# Inputs: only the files that gate G3 hashes (preregistration.md §13), at the
# same paths as phase2.py builds them. No dolt, no Cboe file, no
# volatility_history. raw/yfinance is downloaded data; it is read only here,
# when phase2.py runs under `python -I`.
# =============================================================================

import math
import os
import pathlib
from datetime import date

import pandas as pd

from earnings_vol import schema, store
from earnings_vol.events import calendar
from earnings_vol.ingest import prices, universe
from earnings_vol.measures import run, tables

import synth

# The same paths as phase2.py (VOL, STAGE, CHAIN_DIR); G3 has hashed these files before the loader runs.
VOL = pathlib.Path(os.environ.get("VOL_DATA_DIR", "~/data/vol-projects")).expanduser() / "earnings-vol-study"
STAGE = VOL / "cache/stage/74bed6f4b1281810"
CHAIN_DIR = VOL / "cache/dolt/options@msfqpodh24viv7prdqdan8517rkjp861/option_chain"
WINDOW = (date(2020, 1, 2), date(2026, 10, 26))      # preregistration.md §3; params.yaml data_end

_TABLES: dict = {}


def _null(v) -> bool:
    return v is None or v is pd.NaT or (isinstance(v, float) and math.isnan(v))


def _as_date(v):
    """A python date, or None for a missing value (the stage tables hold python dates already)."""
    if _null(v):
        return None
    if type(v) is date:
        return v
    return pd.Timestamp(v).date()


def _tables() -> dict:
    """The stage tables, read once with the package's own reader and schemas."""
    if not _TABLES:
        _TABLES.update(
            session=store.read_table(STAGE / "session.parquet", schema.SESSION),
            alias=store.read_table(STAGE / "ticker_alias.parquet", schema.TICKER_ALIAS),
            snap=store.read_table(STAGE / "session_snapshot.parquet", schema.SESSION_SNAPSHOT),
            market=store.read_table(STAGE / "market_daily.parquet", schema.MARKET_DAILY),
            events=store.read_table(STAGE / "events.parquet", schema.EVENTS),
            chain=store.read_table(STAGE / "chain_expiry.parquet", schema.CHAIN_EXPIRY),
            daily=store.read_table(STAGE / "iv_daily.parquet", schema.IV_DAILY),
        )
        _TABLES["sessions"] = calendar.Sessions(_TABLES["session"]["session_date"].tolist())
    return _TABLES


def _quotes(sid: str, keep: dict, alias) -> dict:
    """{session: {expiration: ExpiryQuotes}} as measures/run.py run_iv builds them: run.snapshot_quotes on
    every option-chain month file. `keep` maps (security_id, snapshot_date) to the session (status ok or
    stale_repeat), as in run_iv; it holds this name only, which does not change this name's quotes."""
    out = {}
    for path in sorted(CHAIN_DIR.glob("*.parquet")):
        for (s_, d), q in run.snapshot_quotes(path, keep, alias).items():
            if s_ == sid:
                out[d] = q
    return out


def _yahoo(sid: str):
    """(close, exdiv) from raw/yfinance/<symbol>.parquet, as the package's snapshot-close check reads it:
    the close as quoted on its own day (prices.asof_close: Yahoo's split-adjusted close times the later
    split ratios), because the option chain, and so the parity forward, is quoted as traded that day.
    exdiv = the dates with a dividend > 0 (Yahoo's dividend dates are ex-dates). A missing or non-positive
    close is left out, so the forward-vs-close check skips that change."""
    df = prices.load(universe.yahoo_symbol(sid), VOL / "raw")
    days = [_as_date(d) for d in df["date"]]
    close = {}
    for d, c in zip(days, prices.asof_close(df)):
        if d is not None and not _null(c) and c > 0:
            close[d] = float(c)
    exdiv = {d for d, v in zip(days, df["dividends"]) if d is not None and not _null(v) and v > 0}
    return close, exdiv


def load_panel(name: str):
    """Build the name's synth.Panel from the stage exactly as measures/run.py run_iv does: run.snapshot_quotes
    on the option-chain month files (calls and puts merged on strike with an OUTER join: a leg that is not
    in the file has NaN bid and ask = not listed; a leg in the file with bid 0 is listed and fails the
    quote filter); r_cont from market_daily; panel.events = the name's rows of events.parquet as dicts
    (event_id, security_id, announce_date_used, day0_session, exclusion_reason) with python dates and None
    for a missing day 0; anchors from tables.event_anchors; status from session_snapshot; close and exdiv
    from raw/yfinance. Returns (panel, staged_chain_rows, staged_daily_rows). Written at the start of
    phase 2; it computes no statistic, and G4 proves it."""
    t = _tables()
    sessions = t["sessions"]
    sid = name                                   # security_id = ticker for these five names (security.parquet)
    snap = t["snap"][t["snap"]["security_id"] == sid]
    snap = snap[(snap["session_date"] >= WINDOW[0]) & (snap["session_date"] <= WINDOW[1])]
    if snap.empty:
        raise ValueError(f"{name}: no session_snapshot rows in the window")
    status = dict(zip(snap["session_date"], snap["snapshot_status"]))
    days = sorted(status)
    kept = snap[snap["snapshot_status"] != "missing"]
    keep = {(s_, sd_): d for s_, d, sd_ in zip(kept["security_id"], kept["session_date"], kept["snapshot_date"])}
    quotes = _quotes(sid, keep, t["alias"])

    mkt = t["market"]
    rate = dict(zip(mkt["session_date"], mkt["r_cont"]))
    ev = t["events"][t["events"]["security_id"] == sid]
    anchors = tables.event_anchors(ev, sessions).get(sid, [])
    events = [{"event_id": r.event_id, "security_id": r.security_id,
               "announce_date_used": _as_date(r.announce_date_used), "day0_session": _as_date(r.day0_session),
               "exclusion_reason": None if _null(r.exclusion_reason) else r.exclusion_reason}
              for r in ev.itertuples(index=False)]
    close, exdiv = _yahoo(sid)

    panel = synth.Panel(name=sid, sessions=sessions, days=days, quotes=quotes, rate=rate, anchors=anchors,
                        status=status, close=close, exdiv=exdiv, truth={}, events=events)
    staged_chain = t["chain"][t["chain"]["security_id"] == sid].to_dict("records")
    staged_daily = t["daily"][t["daily"]["security_id"] == sid].to_dict("records")
    return panel, staged_chain, staged_daily
