"""Build the snapshot-timing map: the class of every option snapshot session (close, off, late, unknown).

    uv run python tools/snapshot_timing_map.py            # write docs/validation/snapshot-timing/timing_map.json
    uv run python tools/snapshot_timing_map.py --check    # recompute and compare the classes, write nothing

The plan is docs/validation/snapshot-timing/preregistration.md §3. The class of a session comes from the gap between
the option chain's parity spot and the stock's close, across all companies (earnings_vol.stats.snapshot_timing).
No IV and no event measure is read. Inputs, all local:

- ``cache/stage/<params hash>/chain_expiry.parquet`` (the per-expiry forwards; its manifest must name the current
  params), ``session.parquet`` and ``market_daily.parquet`` (r_cont) from the same stage;
- ``$VOL_DATA_DIR/earnings-vol-study/raw/yfinance/<SYM>.parquet`` (closes, dividends, splits).

The JSON holds the rule, the input hashes, counts per year and class, and the lists of off, late and unknown dates.
It holds no per-day or per-company price value.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from earnings_vol import config, params as params_mod, store
from earnings_vol.ingest import prices, universe
from earnings_vol.measures import snapshot_close
from earnings_vol.stats import snapshot_timing as stm

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs/validation/snapshot-timing/timing_map.json"
MIN_TAU = 5  # the nearest expiry with at least 5 sessions to go, as measures/run.py's snapshot-close check


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage_inputs(p) -> tuple[Path, dict]:
    st = config.cache_dir() / "stage" / p.params_hash[:16]
    man = json.loads((st / "chain_expiry.manifest.json").read_text())
    if man["params_hash"] != p.params_hash or man["sha256"] != sha256(st / "chain_expiry.parquet"):
        raise RuntimeError("the staged chain_expiry is not the one of the current params")
    return st, {"params_hash": p.params_hash, "chain_expiry_sha256": man["sha256"], "stage": st.name}


def spots(st: Path, keep=None) -> pd.DataFrame:
    """One row per company and snapshot session: the parity spot S of the nearest expiry with tau >= MIN_TAU, and
    the split-adjusted Yahoo close, previous-session close and open. keep(sid, day) -> bool limits the rows."""
    ce = pd.read_parquet(st / "chain_expiry.parquet",
                         columns=["security_id", "session_date", "expiration", "tau_sessions", "df", "forward",
                                  "status"])
    ce = ce[(ce["status"] == "ok") & (ce["tau_sessions"] >= MIN_TAU)]
    near = ce.sort_values(["security_id", "session_date", "tau_sessions"]) \
        .groupby(["security_id", "session_date"], sort=True).first()
    sessions = sorted(pd.read_parquet(st / "session.parquet")["session_date"])
    prev = dict(zip(sessions[1:], sessions[:-1]))
    mkt = pd.read_parquet(st / "market_daily.parquet")
    rate = dict(zip(mkt["session_date"], mkt["r_cont"]))
    rows = []
    for sid in sorted(near.index.get_level_values(0).unique()):
        y = prices.load(universe.yahoo_symbol(sid), config.raw_dir())
        f = prices.split_factor_after(y)
        close = dict(zip(y["date"], y["close"] * f))
        opens = dict(zip(y["date"], y["open"] * f))
        divs = [(d, v * k) for d, v, k in zip(y["date"], y["dividends"], f) if v > 0]
        for day, r in near.loc[sid].iterrows():
            if keep is not None and not keep(sid, day):
                continue
            if day not in close or prev.get(day) not in close:
                continue
            dv = [((d - day).days, v) for d, v in divs if day < d <= r["expiration"]]
            s = snapshot_close.parity_spot(r["forward"], r["df"], dv, rate[day])
            rows.append({"security_id": sid, "session_date": day, "spot": s, "close": close[day],
                         "prev_close": close[prev[day]], "open": opens.get(day, np.nan)})
    return pd.DataFrame(rows)


def gaps(st: Path) -> pd.DataFrame:
    """One row per company and snapshot session: gap = ln(S_parity / Close), neg_r = -ln(Close_t / Close_{t-1})."""
    s = spots(st)
    return pd.DataFrame({"security_id": s["security_id"], "session_date": s["session_date"],
                         "gap": np.log(s["spot"] / s["close"]), "neg_r": -np.log(s["close"] / s["prev_close"])})


def build() -> dict:
    p = params_mod.load()
    st, inputs = stage_inputs(p)
    g = gaps(st)
    days = []
    for day, grp in g.groupby("session_date", sort=True):
        s = stm.day_stats(grp["gap"], grp["neg_r"])
        days.append({"session_date": day, "cls": stm.classify(s), **s})
    d = pd.DataFrame(days)
    by_year = {str(y): dict(sorted(Counter(grp["cls"]).items())) for y, grp in
               d.groupby(d["session_date"].map(lambda x: x.year))}
    off_like = d["cls"].isin(["off", "late"])
    known = d["cls"] != "unknown"
    margins = {
        # how far the classes sit from the thresholds (aggregates over days, no per-day value)
        "close_max_gap_bp_where_ratio_above": float(d.loc[known & ~off_like & (d["ratio"] > stm.RATIO), "gap_bp"].max()),
        "close_max_ratio_where_gap_above": float(d.loc[known & ~off_like & (d["gap_bp"] > stm.GAP_BP), "ratio"].max()),
        "off_min_gap_bp": float(d.loc[off_like, "gap_bp"].min()),
        "off_min_ratio": float(d.loc[off_like, "ratio"].min()),
        "late_min_slope": float(d.loc[d["cls"] == "late", "slope"].min()),
        "off_max_slope": float(d.loc[d["cls"] == "off", "slope"].max()),
    }
    iso = lambda c: [x.isoformat() for x in d.loc[d["cls"] == c, "session_date"]]  # noqa: E731
    return {
        "kind": "snapshot_timing_map",
        "rule": {"min_firms": stm.MIN_FIRMS, "gap_bp": stm.GAP_BP, "ratio": stm.RATIO, "late_slope": stm.LATE_SLOPE,
                 "min_tau_sessions": MIN_TAU},
        "inputs": inputs,
        "n_sessions": int(len(d)),
        "first_session": d["session_date"].min().isoformat(),
        "last_session": d["session_date"].max().isoformat(),
        "n_firm_sessions": int(len(g)),
        "counts_by_year": by_year,
        "margins": {k: round(v, 4) for k, v in margins.items()},
        "off_dates": iso("off"),
        "late_dates": iso("late"),
        "unknown_dates": iso("unknown"),
        "code_commit": store.code_commit(),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="recompute and compare with the committed map")
    a = ap.parse_args(argv)
    m = build()
    if a.check:
        old = json.loads(OUT.read_text())
        keys = ["rule", "inputs", "counts_by_year", "off_dates", "late_dates", "unknown_dates"]
        bad = [k for k in keys if old.get(k) != m[k]]
        if bad:
            print(f"timing map differs from {OUT.relative_to(REPO)} in: {', '.join(bad)}")
            return 1
        print(f"timing map ok: {len(m['off_dates'])} off, {len(m['late_dates'])} late, "
              f"{len(m['unknown_dates'])} unknown of {m['n_sessions']} sessions")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(m, indent=1, sort_keys=False) + "\n")
    print(f"wrote {OUT.relative_to(REPO)}: {len(m['off_dates'])} off, {len(m['late_dates'])} late, "
          f"{len(m['unknown_dates'])} unknown of {m['n_sessions']} sessions; counts {m['counts_by_year']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
