# =============================================================================
# run.py — run_events(): build the events layer's tables from the ingest
# extracts, check their invariants, and write them.
#
# Run:  uv run python -m earnings_vol.events.run
#
# Reads (all written by ingest/run.py):
#   cache/universe.parquet, cache/dolt/earnings@<commit>/*.parquet,
#   raw/fred/*.csv, raw/yfinance/*.parquet (local, for the gap diagnostic),
#   data/manual/press_release_checks.csv (committed, hand-maintained)
# Writes:
#   cache/stage/<params_hash>/{session,market_daily,security,ticker_alias,
#       events,eps,timing_check}.parquet  + manifests        (every column)
#   data/derived/{session,security,ticker_alias,events,eps}.parquet
#                                          (committed columns only)
#   cache/stage/<params_hash>/events_report.json   counts for the docs
# =============================================================================

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from earnings_vol import config, params as params_mod, schema, store
from earnings_vol.events import calendar, eps as eps_mod, events as events_mod, market, securities, timing
from earnings_vol.ingest import fred, prices, universe

ROOT = Path(__file__).resolve().parents[3]
CHECKS_PATH = ROOT / "data" / "manual" / "press_release_checks.csv"
DERIVED = ROOT / "data" / "derived"


def stage_dir(p) -> Path:
    return config.cache_dir() / "stage" / p.params_hash[:16]


def extract(repo: str, commit: str, table: str) -> pd.DataFrame:
    path = config.cache_dir() / "dolt" / f"{repo}@{commit}" / f"{table}.parquet"
    return pq.read_table(path).to_pandas(date_as_object=True)


def load_inputs(p) -> dict:
    commits = {"earnings": p["dolt"]["earnings_commit"], "options": p["dolt"]["options_commit"]}
    raw = config.raw_dir()
    return {
        "commits": commits,
        "selection": pd.read_parquet(config.cache_dir() / "universe.parquet"),
        "calendar": extract("earnings", commits["earnings"], "earnings_calendar"),
        "eps_history": extract("earnings", commits["earnings"], "eps_history"),
        "eps_estimate": extract("earnings", commits["earnings"], "eps_estimate"),
        "dtb3": fred.parse_series((raw / "fred" / "DTB3.csv").read_text(), "DTB3"),
        "vix": fred.parse_series((raw / "fred" / "VIXCLS.csv").read_text(), "VIXCLS"),
        "checks_text": CHECKS_PATH.read_text(encoding="utf-8"),
    }


def build(p, inp: dict, price_loader) -> dict:
    """Every table of the layer, from in-memory inputs. Pure apart from price_loader."""
    s0, s1 = p.day("sessions", "start"), p.day("sessions", "end")
    session_tbl = calendar.build_session_table(s0, s1, p["snapshot_eras"])
    sessions = calendar.Sessions(session_tbl["session_date"].tolist())
    close_time = dict(zip(session_tbl["session_date"], session_tbl["close_time_et"]))

    data_end = p.day("snapshot_eras", "data_end")
    mkt = market.build_market_daily([d for d in sessions.dates if d <= data_end], inp["dtb3"], inp["vix"])

    security = securities.build_security(inp["selection"])
    aliases = securities.build_ticker_alias(universe.alias_rows(security["security_id"].tolist()))
    uni = set(security.loc[security["in_universe"], "security_id"])

    base = events_mod.base_events(inp["calendar"], aliases, uni)
    checks = timing.parse_checks(inp["checks_text"], sessions, close_time)
    ranges = {k: p.date_range("samples", k) for k in ("daily", "mixed", "coarse")}
    events_mod.check_sample_ranges(ranges)
    em = p["eps_match"]
    ev = events_mod.build_events(base, checks, sessions, calendar_commit=inp["commits"]["earnings"],
                                 sample_ranges=ranges, duplicate_days=int(em["duplicate_within_days"]))

    eps_tbl = eps_mod.build_eps(inp["eps_history"], inp["eps_estimate"], aliases, ev,
                                window_start=em["window_start"], lag_max=int(em["lag_max_days"]),
                                calendar_start=p.day("eps_match", "calendar_start"))
    zones = eps_mod.orphan_zones(eps_tbl, sessions, tuple(p["windows"]["orphan_zone_sessions"]))
    lo = p["windows"]["baseline"][0]
    hi = p["windows"]["event_window"][1]
    ev = events_mod.finish_events(ev, eps_tbl, zones, sessions, (lo, hi))

    # The gap diagnostic, on the label in use (local only).
    spy = price_loader("SPY")
    tc_rows, triggered = [], {}
    gaps_cache = {}
    for r in ev.itertuples(index=False):
        if r.security_id not in gaps_cache:
            gaps_cache[r.security_id] = timing.overnight_gaps(price_loader(universe.yahoo_symbol(r.security_id)), spy)
        row = timing.gap_check(r.announce_date_used, r.timing_used, gaps_cache[r.security_id], sessions, p["gap"])
        triggered[r.event_id] = timing.gap_triggered(row)
        tc_rows.append({"event_id": r.event_id, **row})
    tc = pd.DataFrame(tc_rows, columns=list(schema.TIMING_CHECK.names))
    for c in ("gap_verdict_yf", "outside_flag_yf", "rel_day_max_outside_yf"):
        # Rebuilt from the row dicts: a DataFrame column of ints with None in it
        # would have been turned into floats.
        tc[c] = pd.Series([r[c] for r in tc_rows], dtype=object)

    # The build invariant of ADR 0002 §3: reported always, enforced once the
    # look-ups are declared complete.
    t = p["timing"]
    viol = events_mod.lookup_violations(ev, triggered, sessions, date.fromisoformat(t["lookup_from"]),
                                        int(t["lookup_sessions_before"]), ranges)
    events_mod.enforce_lookup_invariant(viol, bool(t["lookups_complete"]))

    problems = events_mod.check_chain(ev)
    if problems:
        raise RuntimeError(f"prev/next chain broken: {problems[:5]}")
    return {"session": session_tbl, "market_daily": mkt, "security": security, "ticker_alias": aliases,
            "events": ev, "eps": eps_tbl, "timing_check": tc, "lookup_violations": viol, "sessions": sessions}


def report(out: dict, p) -> dict:
    ev, eps_tbl, tc = out["events"], out["eps"], out["timing_check"]
    uni = out["security"][out["security"]["in_universe"]]
    rep = {
        "n_securities": int(len(uni)),
        "n_events": int(len(ev)),
        "events_by_sample": ev["sample"].value_counts().sort_index().to_dict(),
        "timing_status": ev["timing_status"].value_counts().sort_index().to_dict(),
        "exclusion_reason": ev["exclusion_reason"].fillna("(none)").value_counts().sort_index().to_dict(),
        "eps_match_status": eps_tbl["match_status"].value_counts().sort_index().to_dict(),
        "lookup_violations": {
            "n": len(out["lookup_violations"]),
            "by_sample": pd.Series([v["sample"] for v in out["lookup_violations"]]).value_counts().sort_index().to_dict(),
            "by_reason": pd.Series([x for v in out["lookup_violations"] for x in v["reasons"]]).value_counts().sort_index().to_dict(),
        },
        "gap_verdict_on_timing_used": tc["gap_verdict_yf"].fillna("(none)").value_counts().sort_index().to_dict(),
        "lookups_complete": bool(p["timing"]["lookups_complete"]),
    }
    return rep


def main(argv: list[str] | None = None) -> int:
    p = params_mod.load()
    inp = load_inputs(p)
    raw = config.raw_dir()
    out = build(p, inp, lambda sym: prices.load(sym, raw))
    sd = stage_dir(p)
    commits = inp["commits"]
    for name in ("session", "market_daily", "security", "ticker_alias", "events", "eps", "timing_check"):
        table = schema.REGISTRY[name]
        store.write_table(out[name], table, sd / f"{name}.parquet", params_hash=p.params_hash,
                          dolt_commits=commits,
                          extra={"timing_lookups_complete": bool(p["timing"]["lookups_complete"])})
        if table.committed:
            store.write_derived(out[name], table, DERIVED)
    rep = report(out, p)
    (sd / "events_report.json").write_text(json.dumps(rep, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps(rep, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
