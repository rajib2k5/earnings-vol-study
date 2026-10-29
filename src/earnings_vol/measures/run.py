# =============================================================================
# run.py — run_measures(): the measures layer (milestones 1 and 2).
#
# Run:  uv run python -m earnings_vol.measures.run                 (all three)
#       uv run python -m earnings_vol.measures.run --only snapshots
#       uv run python -m earnings_vol.measures.run --only close
#       uv run python -m earnings_vol.measures.run --only iv
#
#   snapshots  `session_snapshot` from every extracted option_chain month:
#              cache/stage/<hash>/session_snapshot.parquet + manifest, and
#              data/derived/session_snapshot.parquet.
#   close      the "snapshot is the close" check on every AMC event of the
#              daily era: cache/stage/<hash>/snapshot_close.json (local:
#              it is built from Yahoo closes; only its summary is reported).
#   iv         milestone 2, in ADR 0001's order chain_expiry -> iv_daily ->
#              event_iv, from the option_chain months, session_snapshot,
#              market_daily (r_cont) and events of this stage:
#                cache/stage/<hash>/chain_expiry.parquet   (local only: it holds
#                    the FRED discount factor, and ~190k rows)
#                cache/stage/<hash>/{iv_daily,event_iv}.parquet + manifests,
#                data/derived/{iv_daily,event_iv}.parquet  (committed columns)
#                cache/stage/<hash>/iv_report.json  counts and the vendor
#                    comparison (P6) for the docs
# =============================================================================

import argparse
import json
import math
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from earnings_vol import config, params as params_mod, schema, store
from earnings_vol.events import calendar, securities
from earnings_vol.events.run import DERIVED, stage_dir
from earnings_vol.ingest import prices, universe
from earnings_vol.measures import chain, event_iv, forward, report, snapshot_close, snapshots, tables, termstructure


def chain_dir(p) -> Path:
    return config.cache_dir() / "dolt" / f"options@{p['dolt']['options_commit']}" / "option_chain"


def run_snapshots(p, sd: Path, sessions, aliases, ids) -> dict:
    digests = []
    for path in sorted(chain_dir(p).glob("*.parquet")):
        chain = pq.read_table(path, columns=["date", "act_symbol", "expiration", "strike", "call_put", "bid", "ask"]) \
            .to_pandas(date_as_object=True)
        digests.append(snapshots.quote_digests(chain))
    dig = pd.concat(digests, ignore_index=True)
    first = date(2020, 1, 2)  # the iv_daily coverage start (data model §3.6)
    last = p.day("snapshot_eras", "data_end")
    table, counts = snapshots.build_session_snapshot(
        dig, lambda t, d: securities.resolve_on(t, d, aliases), ids, sessions, first, last)
    store.write_table(table, schema.SESSION_SNAPSHOT, sd / "session_snapshot.parquet", params_hash=p.params_hash,
                      dolt_commits={"options": p["dolt"]["options_commit"]}, extra={"counts": counts})
    store.write_derived(table, schema.SESSION_SNAPSHOT, DERIVED)
    return counts


def run_close(p, sd: Path, sessions, aliases, ids) -> dict:
    ev = store.read_table(sd / "events.parquet", schema.EVENTS)
    mkt = store.read_table(sd / "market_daily.parquet", schema.MARKET_DAILY)
    r_by_day = dict(zip(mkt["session_date"], mkt["r_cont"]))
    daily_from = p.day("snapshot_eras", "daily_from")
    raw = config.raw_dir()

    # Sessions near any event (D-1 .. next(D)+1) are not "ordinary".
    near: dict[str, set] = {}
    amc_days: dict[str, set] = {}
    for r in ev.itertuples(index=False):
        a = r.announce_date_used
        lo = sessions.prev_before(sessions.first_on_or_after(a))
        hi = sessions.shift(sessions.next_after(a), 1)
        near.setdefault(r.security_id, set()).update(d for d in sessions.dates if lo <= d <= hi)
        if r.timing_used == "AMC" and sessions.is_session(a) and a >= daily_from:
            amc_days.setdefault(r.security_id, set()).add(a)

    px = {}
    for sid in ids:
        df = prices.load(universe.yahoo_symbol(sid), raw)
        factor = prices.split_factor_after(df)
        px[sid] = {"close": dict(zip(df["date"], df["close"] * factor)),
                   "open": dict(zip(df["date"], df["open"] * factor)),
                   "divs": [(d, v * f) for d, v, f in zip(df["date"], df["dividends"], factor) if v > 0]}

    rows = []
    for path in sorted(chain_dir(p).glob("*.parquet")):
        chain = pq.read_table(path, columns=["date", "act_symbol", "expiration", "strike", "call_put", "bid", "ask"]) \
            .to_pandas(date_as_object=True)
        chain = chain[chain["date"] >= daily_from]
        for (sym, day), g in chain.groupby(["act_symbol", "date"], sort=True):
            if not sessions.is_session(day):
                continue
            sid = securities.resolve_on(sym, day, aliases)
            if sid not in px or day not in px[sid]["close"]:
                continue
            # tau = sessions in (day, expiry]: the expiry session counts, the
            # snapshot session does not (ADR 0003 §0 step 5). Usable if >= 5.
            exps = sorted(e for e in g["expiration"].unique()
                          if e > day and sessions.between(day, sessions.as_of(e)) >= 5)
            if not exps:
                continue
            exp = exps[0]
            cal_days = (exp - day).days
            r = r_by_day[day]
            dfac = forward.discount_factor(r, cal_days)
            fw = forward.parity_forward(g[g["expiration"] == exp], dfac)
            if fw is None:
                continue
            divs = [((d - day).days, v) for d, v in px[sid]["divs"] if day < d <= exp]
            s = snapshot_close.parity_spot(fw[0], dfac, divs, r)
            close = px[sid]["close"][day]
            nxt = sessions.next_after(day)
            gap_next = math.log(px[sid]["open"][nxt] / close) if nxt in px[sid]["open"] else np.nan
            kind = "amc_day" if day in amc_days.get(sid, set()) else (
                "ordinary" if day not in near.get(sid, set()) else "other")
            rows.append({"security_id": sid, "date": day, "kind": kind, "diff": math.log(s / close),
                         "gap_next": gap_next, "n_strikes": fw[1]})
    d = pd.DataFrame(rows)
    amc, ordi = d[d["kind"] == "amc_day"], d[d["kind"] == "ordinary"]
    amc_gap = amc.dropna(subset=["gap_next"])
    summary = {
        "n_amc_days": int(len(amc)), "n_amc_events_daily_era": int(sum(len(v) for v in amc_days.values())),
        "n_ordinary_days": int(len(ordi)),
        "median_abs_diff_bp_amc": float(np.median(amc["diff"].abs()) * 1e4),
        "median_abs_diff_bp_ordinary": float(np.median(ordi["diff"].abs()) * 1e4),
        "median_diff_bp_amc": float(np.median(amc["diff"]) * 1e4),
        "median_diff_bp_ordinary": float(np.median(ordi["diff"]) * 1e4),
        "abs_diff_gap_bp": {k: (v * 1e4 if k in ("difference", "ci_lo", "ci_hi") else v) for k, v in
                            snapshot_close.bootstrap_median_gap(amc["diff"].abs(), ordi["diff"].abs()).items()},
        "slope_diff_on_next_gap_amc": snapshot_close.ols_slope(amc_gap["gap_next"], amc_gap["diff"]),
        "median_abs_next_gap_bp_amc": float(np.median(amc_gap["gap_next"].abs()) * 1e4),
        "share_amc_abs_diff_over_1pct": float((amc["diff"].abs() > 0.01).mean()),
        "share_ordinary_abs_diff_over_1pct": float((ordi["diff"].abs() > 0.01).mean()),
    }
    (sd / "snapshot_close.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


QUOTE_COLUMNS = ["date", "act_symbol", "expiration", "strike", "call_put", "bid", "ask", "vol"]


def _expiry_quotes(sub: pd.DataFrame) -> chain.ExpiryQuotes:
    """One expiry's rows (one per strike, calls and puts side by side) as arrays."""
    col = lambda c: sub[c].to_numpy(float)
    return chain.ExpiryQuotes(col("strike"), col("bid_c"), col("ask_c"), col("bid_p"), col("ask_p"), col("vol_c"),
                              col("vol_p"))


def snapshot_quotes(path: Path, keep: dict, aliases) -> dict:
    """{(security_id, session): {expiration: ExpiryQuotes}} for the kept snapshots of one month file.

    `keep` maps (security_id, snapshot_date) to the session the snapshot is
    kept for (session_snapshot, status ok or stale_repeat).
    """
    q = pq.read_table(path, columns=QUOTE_COLUMNS).to_pandas(date_as_object=True)
    pairs = q[["act_symbol", "date"]].drop_duplicates()
    sid = {(t, d): securities.resolve_on(t, d, aliases) for t, d in zip(pairs["act_symbol"], pairs["date"])}
    q["security_id"] = [sid[(t, d)] for t, d in zip(q["act_symbol"], q["date"])]
    q["session_date"] = [keep.get((s_, d)) for s_, d in zip(q["security_id"], q["date"])]
    q = q[q["session_date"].notna()]
    key = ["security_id", "session_date", "expiration", "strike"]
    calls = q[q["call_put"] == "Call"][key + ["bid", "ask", "vol"]]
    puts = q[q["call_put"] == "Put"][key + ["bid", "ask", "vol"]]
    wide = calls.merge(puts, on=key, how="outer", suffixes=("_c", "_p")).sort_values(key, kind="mergesort")
    out: dict = {}
    for (s_, d, e), sub in wide.groupby(["security_id", "session_date", "expiration"], sort=True):
        out.setdefault((s_, d), {})[e] = _expiry_quotes(sub)
    return out


def frame(rows: list[dict], table: schema.Table) -> pd.DataFrame:
    """Rows to a DataFrame in the registry's column order. A nullable int column is
    kept as Python ints and None (pandas would turn it into floats)."""
    df = pd.DataFrame(rows, columns=list(table.names))
    for col in table.columns:
        if col.dtype in ("int16", "int32") and col.nullable:
            df[col.name] = pd.Series([r[col.name] for r in rows], dtype=object)
    return df


def run_iv(p, sd: Path, sessions, aliases, ids) -> dict:
    t0 = time.monotonic()
    ev = store.read_table(sd / "events.parquet", schema.EVENTS)
    mkt = store.read_table(sd / "market_daily.parquet", schema.MARKET_DAILY)
    snap = store.read_table(sd / "session_snapshot.parquet", schema.SESSION_SNAPSHOT)
    rate = dict(zip(mkt["session_date"], mkt["r_cont"]))
    atom_p, term_p = chain.AtomParams.from_params(p["iv"]), termstructure.TermParams.from_params(p["iv"])
    anchors = tables.event_anchors(ev[ev["security_id"].isin(ids)], sessions)
    kept = snap[snap["snapshot_status"] != "missing"]
    keep = {(s_, sd_): d for s_, d, sd_ in zip(kept["security_id"], kept["session_date"], kept["snapshot_date"])}
    stale = {(s_, d) for s_, d, st in zip(kept["security_id"], kept["session_date"], kept["snapshot_status"])
             if st == "stale_repeat"}
    snap_date = dict(zip(zip(kept["security_id"], kept["session_date"]), kept["snapshot_date"]))

    chains: dict = {}
    for path in sorted(chain_dir(p).glob("*.parquet")):
        for (s_, d), quotes in snapshot_quotes(path, keep, aliases).items():
            nxt, _ = tables.neighbours(anchors.get(s_, []), d)
            chains[(s_, d)] = tables.chain_rows(s_, d, snap_date[(s_, d)], (s_, d) in stale, quotes, rate[d],
                                                sessions, nxt, atom_p)
    t_chain = time.monotonic() - t0
    ce_rows = [r for k in sorted(chains) for r in chains[k]]
    ce = frame(ce_rows, schema.CHAIN_EXPIRY)

    daily_rows = [tables.iv_daily_row(r.security_id, r.session_date, r.snapshot_date, r.snapshot_status,
                                      chains.get((r.security_id, r.session_date), []),
                                      anchors.get(r.security_id, []), sessions, term_p)
                  for r in snap.itertuples(index=False)]
    iv = frame(daily_rows, schema.IV_DAILY)
    daily = {(r["security_id"], r["session_date"]): r for r in daily_rows}

    inp = event_iv.EventInputs(daily, chains, rate, sessions, term_p, anchors)
    ev_rows = []
    for r in ev[ev["security_id"].isin(ids)].itertuples(index=False):
        vals, flags = event_iv.event_row(r, inp)
        ev_rows.append({"event_id": r.event_id, **vals, "flags": "|".join(sorted(flags))})
    eiv = frame(ev_rows, schema.EVENT_IV)

    commits = {"options": p["dolt"]["options_commit"], "earnings": p["dolt"]["earnings_commit"]}
    for name, df_ in (("chain_expiry", ce), ("iv_daily", iv), ("event_iv", eiv)):
        table = schema.REGISTRY[name]
        store.write_table(df_, table, sd / f"{name}.parquet", params_hash=p.params_hash, dolt_commits=commits)
        if table.committed:
            store.write_derived(df_, table, DERIVED)
    rep = report.iv_report(ce, iv, eiv, ev)
    rep["seconds"] = {"chain_expiry": round(t_chain, 1), "total": round(time.monotonic() - t0, 1)}
    (sd / "iv_report.json").write_text(json.dumps(rep, indent=2, sort_keys=True, default=str) + "\n")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["snapshots", "close", "iv"], default=None)
    args = ap.parse_args(argv)
    p = params_mod.load()
    sd = stage_dir(p)
    st = store.read_table(sd / "session.parquet", schema.SESSION)
    sessions = calendar.Sessions(st["session_date"].tolist())
    sec = store.read_table(sd / "security.parquet", schema.SECURITY)
    aliases = store.read_table(sd / "ticker_alias.parquet", schema.TICKER_ALIAS)
    ids = sorted(sec.loc[sec["in_universe"], "security_id"])
    if args.only in (None, "snapshots"):
        print(json.dumps(run_snapshots(p, sd, sessions, aliases, ids), indent=2))
    if args.only in (None, "close"):
        print(json.dumps(run_close(p, sd, sessions, aliases, ids), indent=2))
    if args.only in (None, "iv"):
        print(json.dumps(run_iv(p, sd, sessions, aliases, ids), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
