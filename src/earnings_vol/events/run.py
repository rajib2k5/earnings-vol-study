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
#   raw/edgar/*.json and data/manual/edgar_predecessor_ciks.csv, when params
#       timing.edgar is true (fetched beforehand by python -m
#       earnings_vol.ingest.edgar; this stage makes no request)
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
from earnings_vol.ingest import edgar, fred, prices, universe

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


def edgar_scope(viol: list[dict], checks: pd.DataFrame) -> set[str]:
    """The events EDGAR is consulted on: every event the default rule still needs
    looked up (the build invariant's violations), and, for the record only, every
    event with a press-release row (whose release still decides)."""
    pr = {f"{s}:{d.isoformat()}" for s, d in zip(checks["security_id"], checks["announce_date"])}
    return {v["event_id"] for v in viol} | pr


def build(p, inp: dict, price_loader, edgar_loader=None) -> dict:
    """Every table of the layer, from in-memory inputs. Pure apart from the loaders.

    With params timing.edgar true, EDGAR (ADR 0002 §3, source 1) is read for the
    events that need a look-up: a first pass finds them under the default rule
    (press releases, then the calendar label, and the gap trigger on that
    label), and a second pass resolves them from their Item 2.02 8-Ks.
    `edgar_loader(security_id)` returns that security's Item 2.02 8-Ks
    (ingest.edgar.cached_item_202), read from the local cache only.
    """
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
    t = p["timing"]
    spy = price_loader("SPY")
    gaps_cache = {}

    def one_pass(edgar_readings):
        ev = events_mod.build_events(base, checks, sessions, calendar_commit=inp["commits"]["earnings"],
                                     sample_ranges=ranges, duplicate_days=int(em["duplicate_within_days"]),
                                     edgar=edgar_readings)
        outcome = dict(zip(ev["event_id"], ev["edgar_outcome"]))
        eps_tbl = eps_mod.build_eps(inp["eps_history"], inp["eps_estimate"], aliases, ev,
                                    window_start=em["window_start"], lag_max=int(em["lag_max_days"]),
                                    calendar_start=p.day("eps_match", "calendar_start"))
        zones = eps_mod.orphan_zones(eps_tbl, sessions, tuple(p["windows"]["orphan_zone_sessions"]))
        lo = p["windows"]["baseline"][0]
        hi = p["windows"]["event_window"][1]
        ev = events_mod.finish_events(ev, eps_tbl, zones, sessions, (lo, hi))

        # The gap diagnostic, on the label in use (local only).
        tc_rows, triggered = [], {}
        for r in ev.itertuples(index=False):
            if r.security_id not in gaps_cache:
                gaps_cache[r.security_id] = timing.overnight_gaps(
                    price_loader(universe.yahoo_symbol(r.security_id)), spy)
            row = timing.gap_check(r.announce_date_used, r.timing_used, gaps_cache[r.security_id], sessions, p["gap"])
            triggered[r.event_id] = timing.gap_triggered(row)
            tc_rows.append({"event_id": r.event_id, **row})
        tc = pd.DataFrame(tc_rows, columns=list(schema.TIMING_CHECK.names))
        for c in ("gap_verdict_yf", "outside_flag_yf", "rel_day_max_outside_yf"):
            # Rebuilt from the row dicts: a DataFrame column of ints with None in it
            # would have been turned into floats.
            tc[c] = pd.Series([r[c] for r in tc_rows], dtype=object)

        # The build invariant of ADR 0002 §3: reported always, enforced once the
        # look-ups are declared complete (below).
        viol = events_mod.lookup_violations(ev, triggered, sessions, date.fromisoformat(t["lookup_from"]),
                                            int(t["lookup_sessions_before"]), ranges)
        return ev, eps_tbl, tc, triggered, viol, outcome

    ev, eps_tbl, tc, triggered, viol, outcome = one_pass(None)
    edgar_on = bool(t.get("edgar", False))
    pending_gap = []
    if edgar_on:
        if edgar_loader is None:
            raise ValueError("params timing.edgar is true, but no EDGAR loader was given")
        scope = edgar_scope(viol, checks)
        by_id = base.set_index("event_id")
        filings = {sid: edgar_loader(sid) for sid in sorted({by_id.loc[e, "security_id"] for e in scope})}
        readings = {e: edgar.read_acceptance(by_id.loc[e, "announce_date"], filings[by_id.loc[e, "security_id"]],
                                             sessions, close_time) for e in sorted(scope)}
        ev, eps_tbl, tc, triggered, viol, outcome = one_pass(readings)
        # ADR 0002 §3 job 1 under the EDGAR rule: a gap that contradicts the 8-K's
        # label (or the outside flag) asks for a press-release check. Reported, so
        # the check can be made; the 8-K's label stands until a release says otherwise.
        pending_gap = sorted(e for e, src in zip(ev["event_id"], ev["timing_source"])
                             if src == "edgar" and triggered[e])
    events_mod.enforce_lookup_invariant(viol, bool(t["lookups_complete"]))

    problems = events_mod.check_chain(ev)
    if problems:
        raise RuntimeError(f"prev/next chain broken: {problems[:5]}")
    return {"session": session_tbl, "market_daily": mkt, "security": security, "ticker_alias": aliases,
            "events": ev, "eps": eps_tbl, "timing_check": tc, "lookup_violations": viol, "sessions": sessions,
            "edgar_on": edgar_on, "edgar_outcome": outcome, "edgar_pending_gap_checks": pending_gap}


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
        "timing_source": ev["timing_source"].fillna("(none)").value_counts().sort_index().to_dict(),
        "edgar": edgar_report(out) if out.get("edgar_on") else {"on": False},
    }
    return rep


def edgar_report(out: dict) -> dict:
    """What EDGAR gave the events it was consulted on (ADR 0002 §3, source 1)."""
    ev = out["events"].set_index("event_id")
    outcome = {e: o for e, o in out["edgar_outcome"].items() if o is not None}
    s = pd.Series(outcome, dtype=object)
    resolved = [e for e, o in outcome.items() if o in ("confirmed", "inferred")]
    return {
        "on": True,
        "consulted": len(outcome),
        "outcome": s.value_counts().sort_index().to_dict(),
        "resolved_by_label": ev.loc[resolved, "timing_used"].fillna("(non-session D)").value_counts()
                                .sort_index().to_dict(),
        "unresolved_by_sample": {o: ev.loc[[e for e, x in outcome.items() if x == o], "sample"]
                                 .value_counts().sort_index().to_dict()
                                 for o in sorted(set(outcome.values())) if o not in ("confirmed", "inferred",
                                                                                      "press_release")},
        "pending_gap_checks": len(out["edgar_pending_gap_checks"]),
    }


def edgar_loader(selection: pd.DataFrame, raw: Path):
    """security_id -> its Item 2.02 8-Ks under its CIK and any predecessor CIK, read
    from raw/edgar/ only (no request; fetch first with python -m earnings_vol.ingest.edgar)."""
    ciks = dict(zip(selection["security_id"], selection["cik"]))
    pred = edgar.parse_predecessors(edgar.PREDECESSORS_PATH.read_text(encoding="utf-8"))
    return lambda sid: edgar.cached_item_202([ciks[sid], *pred.get(sid, [])], raw)


def main(argv: list[str] | None = None) -> int:
    p = params_mod.load()
    inp = load_inputs(p)
    raw = config.raw_dir()
    out = build(p, inp, lambda sym: prices.load(sym, raw), edgar_loader=edgar_loader(inp["selection"], raw))
    sd = stage_dir(p)
    commits = inp["commits"]
    for name in ("session", "market_daily", "security", "ticker_alias", "events", "eps", "timing_check"):
        table = schema.REGISTRY[name]
        store.write_table(out[name], table, sd / f"{name}.parquet", params_hash=p.params_hash,
                          dolt_commits=commits,
                          extra={"timing_lookups_complete": bool(p["timing"]["lookups_complete"]),
                                 "timing_edgar": bool(out["edgar_on"])})
        if table.committed:
            store.write_derived(out[name], table, DERIVED)
    rep = report(out, p)
    (sd / "events_report.json").write_text(json.dumps(rep, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps(rep, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
